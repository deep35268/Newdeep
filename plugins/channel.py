import re
import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Import database functions safely
try:
    from database.ia_filterdb import save_file
except ImportError:
    try:
        from database.ia_filterdb import Alpha as save_file
    except ImportError:
        def save_file(*args, **kwargs):
            pass

def get_config(key, default):
    val = os.environ.get(key)
    if val is not None:
        return val
    try:
        import info
        if hasattr(info, key): return getattr(info, key)
    except ImportError: pass
    try:
        import config
        if hasattr(config, key): return getattr(config, key)
    except ImportError: pass
    return default

CHANNELS = [-1003954712996]
raw_channels = get_config("CHANNELS", None)
if raw_channels:
    if isinstance(raw_channels, list): CHANNELS = raw_channels
    elif isinstance(raw_channels, (int, float)): CHANNELS = [int(raw_channels)]
    else: CHANNELS = [int(v.strip()) for v in re.split(r'[,\s]+', str(raw_channels)) if v.strip().replace('-', '').replace('+', '').isdigit()]

UPDATES_CHANNEL = -1003752618894
raw_updates = get_config("MOVIE_UPDATE_CHANNEL", get_config("LOG_CHANNEL", "-1002427494480"))
try:
    if isinstance(raw_updates, list): UPDATES_CHANNEL = int(raw_updates[0])
    else: UPDATES_CHANNEL = int(raw_updates)
except Exception: pass

REQUEST_GROUP_LINK = get_config("REQUEST_GROUP_LINK", "https://t.me/+WtlAyRpidLExMDE1")
REQUEST_GROUP_NAME = get_config("REQUEST_GROUP_NAME", "PROJECT GROUP")

POSTED_MOVIES = set()

QUALITY_KEYWORDS = [
    "2160p", "1080p", "720p", "480p", "360p", "4k", "uhd", "bluray", 
    "web-dl", "webdl", "webrip", "hdrip", "brrip", "dvdrip", "hdtv", "x264", "x265", "hevc"
]

AUDIO_PATTERNS = {
    "hindi": "Hindi", "english": "English", "eng": "English", "tamil": "Tamil",
    "telugu": "Telugu", "bengali": "Bengali", "marathi": "Marathi", "kannada": "Kannada",
    "malayalam": "Malayalam", "punjabi": "Punjabi", "dual": "Dual Audio", "multi": "Multi Audio"
}

def clean_movie_title(filename: str):
    """
    ਸੁਪਰ ਐਡਵਾਂਸਡ ਫਿਲਟਰ: ਇਹ ਫਾਈਲ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਹਰ ਤਰ੍ਹਾਂ ਦਾ ਕੂੜਾ ਸਾਫ਼ ਕਰਕੇ 
    ਸਿਰਫ਼ ਅਤੇ ਸਿਰਫ਼ ਫਿਲਮ ਦਾ ਅਸਲੀ ਨਾਮ ਬਾਹਰ ਕੱਢਦਾ ਹੈ।
    """
    name = str(filename)
    
    # 1. ਐਕਸਟੈਂਸ਼ਨ ਹਟਾਓ (.mkv, .mp4)
    name = re.sub(r"\.(mkv|mp4|avi|webm|mov)$", "", name, flags=re.IGNORECASE)
    
    # 2. ਟੈਲੀਗ੍ਰਾਮ ਯੂਜ਼ਰਨੇਮ ਅਤੇ ਲਿੰਕ ਸਾਫ਼ ਕਰੋ
    name = re.sub(r"@[\w_]+", " ", name)
    name = re.sub(r"https?://\S+", " ", name)
    name = re.sub(r"\[.*?\]|\(.*?\)", " ", name) # ਬਰੈਕਟਾਂ ਦੇ ਅੰਦਰਲਾ ਸਭ ਕੁਝ ਸਾਫ਼ ਕਰੋ
    
    # 3. ਬਿੰਦੀਆਂ (Dots) ਅਤੇ ਡੈਸ਼ ਨੂੰ ਸਪੇਸ ਵਿੱਚ ਬਦਲੋ
    name = name.replace(".", " ").replace("_", " ").replace("-", " ")
    
    # 4. ਆਡੀਓ ਭਾਸ਼ਾਵਾਂ ਪਛਾਣੋ
    found_audios = []
    name_lower = name.lower()
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", name_lower):
            if val not in found_audios: found_audios.append(val)
    if not found_audios: found_audios = ["Hindi"]
    
    is_org = bool(re.search(r"\b(org|original)\b", name_lower))
    
    # 5. ਸਾਲ (Year) ਲੱਭੋ
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name)
    year = year_match.group(1) if year_match else ""
    
    # 6. ਨਾਮ ਨੂੰ ਕੁਆਲਿਟੀ ਕੀਵਰਡਸ ਜਾਂ ਸਾਲ ਵਾਲੀ ਜਗ੍ਹਾ ਤੋਂ ਬਿਲਕੁਲ ਕੱਟ ਦਿਓ
    cutoff = len(name)
    if year_match:
        cutoff = min(cutoff, year_match.start())
        
    for kw in QUALITY_KEYWORDS:
        match = re.search(rf"\b{kw}\b", name_lower)
        if match:
            cutoff = min(cutoff, match.start())
            
    clean_title = name[:cutoff].strip()
    # ਜੇਕਰ ਨਾਮ ਖਾਲੀ ਹੋ ਜਾਵੇ ਤਾਂ ਅਸਲੀ ਨਾਮ ਰੱਖੋ
    if not clean_title:
        clean_title = name.strip()
        
    # ਫਾਲਤੂ ਡਬਲ ਸਪੇਸ ਹਟਾਓ
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    return clean_title, year, found_audios, is_org

async def fetch_perfect_data(title: str, year: str):
    """
    Mubi API + OMDb API ਦਾ ਸਾਂਝਾ ਨੈੱਟਵਰਕ ਜੋ 100% ਸਹੀ Landscape ਪੋਸਟਰ ਅਤੇ IMDb Rating ਲਿਆਉਂਦਾ ਹੈ।
    """
    poster_url = None
    imdb_rating = "N/A"
    
    async with aiohttp.ClientSession() as session:
        # 1. IMDb ਰੇਟਿੰਗ ਅਤੇ Landscape ਪੋਸਟਰ ਲਈ ਓਪਨ ਡਾਟਾਬੇਸ ਦੀ ਵਰਤੋਂ
        try:
            # ਸਪੇਸ ਨੂੰ ਪਲੱਸ (+) ਵਿੱਚ ਬਦਲੋ
            search_title = title.replace(" ", "+")
            omdb_url = f"http://www.omdbapi.com/?t={search_title}&y={year}&apikey=6a32cb2"
            
            async with session.get(omdb_url, timeout=6) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("Response") == "True":
                        # ਰੇਟਿੰਗ ਸੈੱਟ ਕਰਨਾ
                        rating = data.get("imdbRating", "N/A")
                        if rating != "N/A":
                            imdb_rating = f"{rating}/10"
                        
                        # ਪੋਸਟਰ ਲਿੰਕ ਲੈਣਾ
                        api_poster = data.get("Poster")
                        if api_poster and api_poster.startswith("http"):
                            # ਜਾਦੂਈ ਫਿਲਟਰ: ਵਰਟੀਕਲ ਪੋਸਟਰ ਨੂੰ ਬੈਕਗ੍ਰਾਊਂਡ ਬਲਰ ਦੇ ਕੇ ਸੁੰਦਰ HD Landscape (1280x720) ਬੈਨਰ ਵਿੱਚ ਬਦਲਣਾ
                            poster_url = f"https://images.weserv.nl/?url={api_poster}&w=1280&h=720&fit=contain&bg=black"
        except Exception as e:
            print(f"OMDb Error: {e}")

        # 2. ਬੈਕਅੱਪ ਸਿਸਟਮ: ਜੇਕਰ OMDb ਫੇਲ੍ਹ ਹੁੰਦਾ ਹੈ, ਤਾਂ iTunes ਰਾਹੀਂ ਪੋਸਟਰ ਬਣਾਉਣਾ
        if not poster_url:
            try:
                itunes_url = "https://itunes.apple.com/search"
                params = {"term": f"{title} {year}".strip(), "entity": "movie", "limit": 1}
                async with session.get(itunes_url, params=params, timeout=5) as r:
                    if r.status == 200:
                        res = await r.json()
                        results = res.get("results", [])
                        if results and results[0].get("artworkUrl100"):
                            itunes_poster = results[0]["artworkUrl100"].replace("100x100bb.jpg", "600x600bb.jpg")
                            poster_url = f"https://images.weserv.nl/?url={itunes_poster}&w=1280&h=720&fit=contain&bg=black"
            except Exception:
                pass

    return poster_url, imdb_rating

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def media(bot: Client, message: Message):
    media_file = message.document or message.video or message.audio
    if not media_file: return

    try:
        await save_file(message)
    except Exception as dbe:
        print(f"DB Save failure: {dbe}")

    file_name = getattr(media_file, "file_name", "movie.mp4") or "movie.mp4"
    
    # ਨਾਮ ਨੂੰ ਬਿਲਕੁਲ ਸ਼ੀਸ਼ੇ ਵਾਂਗ ਸਾਫ਼ ਕਰਨਾ
    title, year, audios, is_org = clean_movie_title(file_name)

    movie_unique_key = f"{title.lower()}_{year}"
    if movie_unique_key in POSTED_MOVIES:
        return
    POSTED_MOVIES.add(movie_unique_key)

    # ਪੋਸਟਰ ਅਤੇ ਰੇਟਿੰਗ ਲੱਭੋ
    poster, imdb_rating = await fetch_perfect_data(title, year)

    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    year_str = f" {year}" if year else ""
    
    # ਤੁਹਾਡਾ ਪਰਫੈਕਟ ਫਾਰਮੈਟ
    caption_text = (
        f"🎬 `{title}{year_str}`\n\n"
        f"⭐ IMDb: {imdb_rating}\n\n"
        f"📌 (Touch To Copy)\n\n"
        f"➡ Audio Track:- 🔊 {audio_tags}{org_badge}\n\n"
        f"Added ✅"
    )

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 {REQUEST_GROUP_NAME} 🔰", url=REQUEST_GROUP_LINK)]
    ])
    
    # ਫਾਲਬੈਕ ਥੰਬਨੇਲ ਸਿਰਫ਼ ਉਦੋਂ ਜਦੋਂ ਇੰਟਰਨੈੱਟ 'ਤੇ ਕੁਝ ਵੀ ਨਾ ਹੋਵੇ
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            try: poster = await bot.download_media(media_file.thumbs[0].file_id)
            except Exception: poster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1280"
        else:
            poster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1280"

    try:
        await bot.send_photo(
            chat_id=UPDATES_CHANNEL,
            photo=poster,
            caption=caption_text,
            reply_markup=reply_markup
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await bot.send_photo(chat_id=UPDATES_CHANNEL, photo=poster, caption=caption_text, reply_markup=reply_markup)
    except Exception as e:
        print(f"Post sending failed: {e}")
    finally:
        if poster and not poster.startswith("http") and os.path.exists(poster):
            try: os.remove(poster)
            except Exception: pass

    await asyncio.sleep(15)
    POSTED_MOVIES.discard(movie_unique_key)
