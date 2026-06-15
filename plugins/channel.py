import re
import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Import the existing DB save_file function from your database engine
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
        if hasattr(info, key):
            return getattr(info, key)
    except ImportError:
        pass
    try:
        import config
        if hasattr(config, key):
            return getattr(config, key)
    except ImportError:
        pass
    return default

# Safely resolve Database Channels 
raw_channels = get_config("CHANNELS", None)
if isinstance(raw_channels, list):
    CHANNELS = raw_channels
elif isinstance(raw_channels, (int, float)):
    CHANNELS = [int(raw_channels)]
else:
    CHANNELS = [int(v.strip()) for v in re.split(r'[,\s]+', str(raw_channels)) if v.strip().replace('-', '').replace('+', '').isdigit()]

if not CHANNELS:
    CHANNELS = [-1003954712996] 

# Safely resolve Updates posting channel
raw_updates = get_config("MOVIE_UPDATE_CHANNEL", get_config("LOG_CHANNEL", "-1002427494480"))
try:
    if isinstance(raw_updates, list):
        UPDATES_CHANNEL = int(raw_updates[0])
    else:
        UPDATES_CHANNEL = int(raw_updates)
except (ValueError, TypeError, IndexError):
    UPDATES_CHANNEL = -1003752618894 

# Configuration options
REQUEST_GROUP_LINK = get_config("REQUEST_GROUP_LINK", "https://t.me/+WtlAyRpidLExMDE1")
REQUEST_GROUP_NAME = get_config("REQUEST_GROUP_NAME", "PROJECT GROUP")
USE_TMDB_POSTER = str(get_config("USE_TMDB_POSTER", "True")).lower() in ("true", "1", "yes")
TMDB_API_KEY = get_config("TMDB_API_KEY", "db55323b8d3e4154498498a75642b381")

# ਗਲਤੀਆਂ ਨੂੰ ਰੋਕਣ ਲਈ ਗਲੋਬਲ ਲਿਸਟ (ਤਾਂ ਜੋ ਇੱਕੋ ਫਿਲਮ ਦਾ ਪੋਸਟਰ ਬਾਰ-ਬਾਰ ਨਾ ਜਾਵੇ)
POSTED_MOVIES = set()

QUALITY_PATTERNS = [
    "2160p", "1080p", "720p", "480p", "360p", "4k", "ultrahd", "hdr", 
    "bluray", "web-dl", "webdl", "webrip", "hdrip", "brrip", "dvdrip"
]

AUDIO_PATTERNS = {
    "hindi": "Hindi", "english": "English", "eng": "English", "tamil": "Tamil",
    "telugu": "Telugu", "bengali": "Bengali", "marathi": "Marathi", "kannada": "Kannada",
    "malayalam": "Malayalam", "punjabi": "Punjabi", "dual": "Dual Audio", "multi": "Multi Audio"
}

def parse_filename(filename: str):
    clean = str(filename)
    
    clean = re.sub(r"\[\s*@?[\w_]+\s*\]", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\[\s*(https?://)?(t\.me|telegram\.me)/[\w_]+\s*\]", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\(\s*(https?://)?(t\.me|telegram\.me)/[\w_]+\s*\)", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\b(https?://)?(t\.me|telegram\.me)/[\w_]+\b", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"@[\w_]+", " ", clean)

    clean = re.sub(r"\.(mkv|mp4|avi|webm|mov|3gp)$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"[\._\-]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
    year = year_match.group(1) if year_match else ""

    found_qualities = []
    clean_lower = clean.lower()
    for q in QUALITY_PATTERNS:
        if re.search(rf"\b{q}\b", clean_lower):
            found_qualities.append(q.upper())
    quality = " ".join(found_qualities) if found_qualities else "HDRip"

    found_audios = []
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", clean_lower):
            if val not in found_audios:
                found_audios.append(val)
    if not found_audios:
        found_audios = ["Hindi"]

    is_org = bool(re.search(r"\b(org|original)\b", clean_lower))

    title = clean
    cutoff = len(title)
    if year_match:
        idx = title.find(year)
        if idx != -1 and idx < cutoff:
            cutoff = idx
            
    for q in QUALITY_PATTERNS:
        match = re.search(rf"\b{q}\b", title, re.IGNORECASE)
        if match and match.start() < cutoff:
            cutoff = match.start()
            
    if cutoff > 0:
        title = title[:cutoff]
        
    title = re.sub(r"\s+", " ", title).strip() or "Unknown Movie"
    return title, year, found_audios, quality, is_org

async def fetch_movie_poster(title: str, year: str) -> str:
    async with aiohttp.ClientSession() as session:
        if USE_TMDB_POSTER and TMDB_API_KEY:
            try:
                search_url = "https://api.themoviedb.org/3/search/movie"
                params = {"api_key": TMDB_API_KEY, "query": title}
                if year:
                    params["year"] = year

                async with session.get(search_url, params=params, timeout=10) as r:
                    if r.status == 200:
                        data = await r.json()
                        results = data.get("results", [])
                        if results:
                            movie = results[0]
                            if movie.get("backdrop_path"):
                                return f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
                            if movie.get("poster_path"):
                                return f"https://image.tmdb.org/t/p/w1280{movie['poster_path']}"
            except Exception as e:
                print(f"TMDB Poster Error: {e}")

        try:
            itunes_url = "https://itunes.apple.com/search"
            term = f"{title} {year}".strip()
            params = {"term": term, "entity": "movie", "limit": 1}

            async with session.get(itunes_url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results", [])
                    if results and results[0].get("artworkUrl100"):
                        return results[0]["artworkUrl100"].replace("100x100bb.jpg", "1000x1000bb.jpg")
        except Exception as e:
            print(f"iTunes Error: {e}")

    return None
    
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def media(bot: Client, message: Message):
    media_file = None
    if message.document:
        media_file = message.document
        media_file.file_type = "document"
    elif message.video:
        media_file = message.video
        media_file.file_type = "video"
    elif message.audio:
        media_file = message.audio
        media_file.file_type = "audio"
    
    if not media_file:
        return

    # 1. ਡਾਟਾ ਹਮੇਸ਼ਾ DB ਵਿੱਚ ਸੇਵ ਹੋਵੇਗਾ (ਚਾਹੇ ਕੋਈ ਵੀ ਕੁਆਲਿਟੀ ਹੋਵੇ)
    try:
        await save_file(message)
    except Exception as dbe:
        print(f"DB Save failure: {dbe}")

    file_name = getattr(media_file, "file_name", "movie_file.mp4") or "movie_file.mp4"
    title, year, audios, quality, is_org = parse_filename(file_name)

    # ਇੱਕ ਵਿਲੱਖਣ ਆਈਡੀ (Unique ID) ਬਣਾਉਣਾ ਤਾਂ ਜੋ ਪਤਾ ਲੱਗ ਸਕੇ ਕਿ ਇਹ ਫਿਲਮ ਪਹਿਲਾਂ ਭੇਜੀ ਗਈ ਹੈ ਜਾਂ ਨਹੀਂ
    movie_unique_key = f"{title.lower()}_{year}"

    # 2. ਚੈੱਕ ਕਰੋ ਜੇਕਰ ਇਸ ਫਿਲਮ ਦਾ ਪੋਸਟਰ ਪਹਿਲਾਂ ਹੀ ਭੇਜਿਆ ਜਾ ਚੁੱਕਾ ਹੈ, ਤਾਂ ਇੱਥੇ ਹੀ ਰੁਕ ਜਾਓ (ਸਿੰਗਲ ਪੋਸਟਰ ਨਿਯਮ)
    if movie_unique_key in POSTED_MOVIES:
        return
        
    # ਜੇਕਰ ਨਵੀਂ ਫਿਲਮ ਹੈ, ਤਾਂ ਇਸਨੂੰ ਲਿਸਟ ਵਿੱਚ ਜੋੜੋ
    POSTED_MOVIES.add(movie_unique_key)

    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    year_str = f"({year})" if year else ""
    
    caption_text = f"**{title} {year_str}**\n\n** ➥ AUDIO TRACK:-** 🔊 {audio_tags}{org_badge}\n\nAdded ✅"

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 {REQUEST_GROUP_NAME} 🔰", url=REQUEST_GROUP_LINK)]
    ])

    poster = await fetch_movie_poster(title, year)
    
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            try:
                poster = await bot.download_media(media_file.thumbs[0].file_id)
            except Exception:
                poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500"
        else:
            poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500"

    try:
        # ਸਿਰਫ਼ ਇੱਕ ਵਾਰ ਪੋਸਟਰ ਚੈਨਲ ਵਿੱਚ ਜਾਵੇਗਾ
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
        print(f"Channel update failed to send photo: {e}")
    finally:
        if poster and not poster.startswith("http") and os.path.exists(poster):
            try:
                os.remove(poster)
            except Exception:
                pass

    # 10 ਸਕਿੰਟਾਂ ਬਾਅਦ ਮੈਮੋਰੀ ਸਾਫ਼ ਕਰੋ ਤਾਂ ਜੋ ਭਵਿੱਖ ਵਿੱਚ ਜੇਕਰ ਉਹੀ ਫਿਲਮ ਦੁਬਾਰਾ ਅਪਲੋਡ ਹੋਵੇ ਤਾਂ ਨਵਾਂ ਪੋਸਟਰ ਜਾ ਸਕੇ
    await asyncio.sleep(10)
    POSTED_MOVIES.discard(movie_unique_key)
