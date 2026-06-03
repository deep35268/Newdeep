import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
import asyncio
from datetime import datetime

# info.py ਵਿੱਚੋਂ ਸੈਟਿੰਗਾਂ ਇੰਪੋਰਟ ਕਰਨਾ
try:
    from info import UPDATES_CHANNEL, DATABASE_CHANNEL, REQUEST_GROUP_LINK, REQUEST_GROUP_NAME, USE_TMDB_POSTER, TMDB_API_KEY
except ImportError:
    # ਜੇਕਰ ਇੰਪੋਰਟ ਨਾ ਹੋਵੇ ਤਾਂ ਡਿਫੌਲਟ ਵੈਲਯੂ
    UPDATES_CHANNEL = -1002222222222
    DATABASE_CHANNEL = -1001111111111
    REQUEST_GROUP_LINK = "https://t.me/MovieRequestGroup"
    REQUEST_GROUP_NAME = "MOVIE REQUEST GROUP"
    USE_TMDB_POSTER = False
    TMDB_API_KEY = ""

# ਫਾਈਲ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਕੁਆਲਿਟੀ ਲੱਭਣ ਲਈ ਸੂਚੀ
QUALITY_PATTERNS = [
    r"2160p", r"1080p", r"720p", r"480p", r"360p", 
    r"4k", r"ultrahd", r"hdr", r"bluray", r"web-dl", r"webdl", r"webrip", r"hdrip", r"brrip", r"dvdrip"
]

# ਫਾਈਲ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਆਡੀਓ ਲੱਭਣ ਲਈ ਸੂਚੀ
AUDIO_PATTERNS = {
    "hindi": "Hindi",
    "english": "English",
    "eng": "English",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "bengali": "Bengali",
    "marathi": "Marathi",
    "kannada": "Kannada",
    "malayalam": "Malayalam",
    "punjabi": "Punjabi",
    "dual": "Dual Audio",
    "multi": "Multi Audio"
}

def parse_filename(filename: str):
    """
    ਇਹ ਫੰਕਸ਼ਨ ਮੂਵੀ ਫਾਈਲ ਦੇ ਟਾਈਟਲ, ਸਾਲ, ਕੁਆਲਿਟੀ ਅਤੇ ਆਡੀਓ ਨੂੰ ਆਪਣੇ ਆਪ ਵੱਖ ਕਰਦਾ ਹੈ।
    """
    # ਐਕਸਟੈਂਸ਼ਨ ਹਟਾਓ (ਜਿਵੇਂ .mkv, .mp4)
    clean = re.sub(r"\.(mkv|mp4|avi|webm)$", "", filename, flags=re.IGNORECASE)
    # ਡੌਟਸ (dots) ਅਤੇ ਡੈਸ਼ਾਂ ਨੂੰ ਸਪੇਸ ਵਿੱਚ ਬਦਲੋ
    clean = re.sub(r"[\._\-]", " ", clean)

    # 1. ਸਾਲ (Year) ਲੱਭੋ
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
    year = year_match.group(1) if year_match else str(datetime.now().year)

    # 2. ਕੁਆਲਿਟੀ ਲੱਭੋ
    found_qualities = []
    clean_lower = clean.lower()
    for q in QUALITY_PATTERNS:
        if re.search(rf"\b{q}\b", clean_lower):
            found_qualities.append(q.upper())
    quality = " ".join(found_qualities) if found_qualities else "HDRip"

    # 3. ਆਡੀਓ ਲੱਭੋ
    found_audios = []
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", clean_lower):
            if val not in found_audios:
                found_audios.append(val)
                
    if not found_audios:
        found_audios = ["Hindi"]  # ਜੇਕਰ ਕੋਈ ਆਡੀਓ ਨਾ ਮਿਲੇ ਤਾਂ ਡਿਫੌਲਟ ਹਿੰਦੀ

    # 4. ਚੈੱਕ ਕਰੋ ਕਿ ਓਰੀਜਨਲ ਆਡੀਓ (#ORG) ਹੈ ਜਾਂ ਨਹੀਂ
    is_org = bool(re.search(r"\b(org|original)\b", clean_lower))

    # 5. ਫਾਈਲ ਦੇ ਨਾਮ ਤੋਂ ਮੂਵੀ ਦਾ ਅਸਲੀ ਟਾਈਟਲ ਕੱਢੋ (ਸਾਲ/ਕੁਆਲਿਟੀ ਤੋਂ ਪਹਿਲਾਂ ਵਾਲਾ ਹਿੱਸਾ)
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
        
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        title = "Unknown Movie"

    return title, year, found_audios, quality, is_org

async def fetch_movie_poster(title: str, year: str) -> str:
    """
    ਇੰਟਰਨੈੱਟ (TMDb API) ਤੋਂ ਮੂਵੀ ਦਾ ਅਸਲੀ ਪੋਸਟਰ ਲੱਭਣਾ
    """
    if not USE_TMDB_POSTER or not TMDB_API_KEY:
        return None
        
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
        "year": year
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results")
                    if results:
                        poster_path = results[0].get("poster_path")
                        if poster_path:
                            return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception:
        pass
    return None

# ਜਦੋਂ ਡਾਟਾਬੇਸ ਚੈਨਲ ਵਿੱਚ ਕੋਈ ਫਾਈਲ (Document ਜਾਂ Video) ਆਵੇਗੀ, ਇਹ ਫੰਕਸ਼ਨ ਆਪਣੇ ਆਪ ਚੱਲੇਗਾ
@Client.on_message(filters.chat(DATABASE_CHANNEL) & (filters.document | filters.video))
async def on_db_channel_forward(client: Client, message: Message):
    # ਫਾਈਲ ਦਾ ਨਾਮ ਲੱਭੋ
    file_name = None
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name or "video.mp4"
        
    if not file_name:
        return # ਜੇਕਰ ਫਾਈਲ ਦਾ ਨਾਮ ਨਾ ਮਿਲੇ ਤਾਂ ਕੁਝ ਨਾ ਕਰੋ

    # ਫਾਈਲ ਦੇ ਨਾਮ ਨੂੰ ਪਾਰਸ (Parse) ਕਰੋ
    title, year, audios, quality, is_org = parse_filename(file_name)

    # ਪੰਜਾਬੀ/ਹਿੰਦੀ ਆਡੀਓ ਟੈਗਸ ਤਿਆਰ ਕਰੋ
    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    full_audio_info = f"🔊 {audio_tags}{org_badge}"

    # TMDB ਤੋਂ ਪੋਸਟਰ ਲੱਭੋ
    poster_photo = await fetch_movie_poster(title, year)
    
    # ਜੇਕਰ ਪੋਸਟਰ ਇੰਟਰਨੈੱਟ ਤੋਂ ਨਹੀਂ ਮਿਲਦਾ, ਤਾਂ ਵੀਡੀਓ ਦਾ ਥੰਬਨਾਈਲ ਵਰਤੋ
    if not poster_photo:
        if message.video and message.video.thumbs:
            poster_photo = message.video.thumbs[0].file_id
        elif message.document and message.document.thumbs:
            poster_photo = message.document.thumbs[0].file_id
        else:
            # ਡਿਫੌਲਟ ਬੈਕਗ੍ਰਾਊਂਡ ਪਿਕਚਰ
            poster_photo = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500"

    # ਪੋਸਟ ਦਾ ਫਾਰਮੈਟ (ਜੋ ਚੈਨਲ ਵਿੱਚ ਜਾਵੇਗਾ)
    caption = (
        f"**{title} {year} (Touch To Copy)**\n\n"
        f"**➥ AUDIO TRACK:-** {full_audio_info}\n"
        f"**➥ QUALITY:-** #{quality}\n\n"
        f"Added ✅"
    )

    # ਗਰੁੱਪ ਦਾ ਬਟਨ ਤਿਆਰ ਕਰੋ
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 MOVIE REQUEST GROUP 🔰", url="https://t.me/+WtlAyRpidLExMDE1")]
    ])

    try:
        # ਅਪਡੇਟ ਚੈਨਲ ਵਿੱਚ ਫੋਟੋ ਅਤੇ ਕੈਪਸ਼ਨ ਭੇਜਣਾ
        if poster_photo:
            await client.send_photo(
                chat_id=UPDATES_CHANNEL,
                photo=poster_photo,
                caption=caption,
                reply_markup=markup
            )
        else:
            await client.send_message(
                chat_id=UPDATES_CHANNEL,
                text=caption,
                reply_markup=markup,
                disable_web_page_preview=False
            )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        # ਕੁਝ ਸਕਿੰਟਾਂ ਬਾਅਦ ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ
        await client.send_photo(
            chat_id=UPDATES_CHANNEL,
            photo=poster_photo,
            caption=caption,
            reply_markup=markup
        )
    except Exception as e:
        print(f"Auto-Poster Error: {e}")
