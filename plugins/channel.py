import re
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# info.py ਤੋਂ ਕੌਨਫਿਗ੍ਰੇਸ਼ਨ ਇੰਪੋਰਟਸ
from info import CHANNELS, UPDATES_CHANNEL, REQUEST_GROUP_LINK, REQUEST_GROUP_NAME, USE_TMDB_POSTER, TMDB_API_KEY
# ਤੁਹਾਡੇ ਬੋਟ ਦਾ ਡਾਟਾਬੇਸ ਸੇਵ ਫੰਕਸ਼ਨ
from database.ia_filterdb import save_file

# ਫਾਈਲਨੇਮ ਵਿੱਚੋਂ ਕੁਆਲਿਟੀ ਅਤੇ ਆਡੀਓ ਟ੍ਰੈਕ ਲੱਭਣ ਲਈ ਪੈਟਰਨ
QUALITY_PATTERNS = [
    r"2160p", r"1080p", r"720p", r"480p", r"360p", 
    r"4k", r"ultrahd", r"hdr", r"bluray", r"web-dl", r"webdl", r"webrip", r"hdrip", r"brrip", r"dvdrip", r"hq", r"s-print", r"s print"
]

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
    "bhojpuri": "Bhojpuri",
    "punjabi": "Punjabi",
    "dual": "Dual Audio",
    "multi": "Multi Audio"
}

def parse_filename(filename: str):
    """
    ਟੋਰੈਂਟ ਵਰਗੇ ਨਾਮਾਂ ਵਿੱਚੋਂ ਮੂਵੀ ਟਾਈਟਲ, ਸਾਲ, ਆਡੀਓ ਅਤੇ ਕੁਆਲਿਟੀ ਅਲੱਗ ਕਰਦਾ ਹੈ।
    """
    # ਐਕਸਟੈਨਸ਼ਨ ਹਟਾਓ
    clean = re.sub(r"\.(mkv|mp4|avi|webm|mov|3gp)$", "", filename, flags=re.IGNORECASE)
    # ਬਿੰਦੀਆਂ ਅਤੇ ਅੰਡਰਸਕੋਰ ਹਟਾਓ
    clean = re.sub(r"[\._\-]", " ", clean)

    # 1. ਰਿਲੀਜ਼ ਸਾਲ ਲੱਭੋ
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
    year = year_match.group(1) if year_match else "2025"

    # 2. ਕੁਆਲਿਟੀ ਲੱਭੋ
    found_qualities = []
    clean_lower = clean.lower()
    for q in QUALITY_PATTERNS:
        if re.search(rf"\b{q}\b", clean_lower):
            found_qualities.append(q.upper())
    quality = " ".join(found_qualities) if found_qualities else "HDRip"

    # 3. ਆਡੀਓ ਟ੍ਰੈਕਸ ਲੱਭੋ
    found_audios = []
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", clean_lower):
            if val not in found_audios:
                found_audios.append(val)
                
    if not found_audios:
        found_audios = ["Hindi"]  # ਡਿਫਾਲਟ ਆਡੀਓ

    # 4. ਕੀ ਆਡੀਓ ਓਰੀਜਨਲ (ORG) ਹੈ?
    is_org = bool(re.search(r"\b(org|original)\b", clean_lower))

    # 5. ਮੂਵੀ ਦਾ ਸਾਫ਼ ਟਾਈਟਲ ਕੱਢੋ
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
    """TMDb API ਤੋਂ ਅਸਲੀ ਮੂਵੀ ਪੋਸਟਰ ਲਿਆਉਂਦਾ ਹੈ"""
    if not USE_TMDB_POSTER or not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        return None
        
    url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": title, "year": year}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results")
                    if results and results[0].get("poster_path"):
                        return f"https://image.tmdb.org/t/p/w500{results[0].get('poster_path')}"
    except Exception:
        pass
    return None


@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video))
async def media(bot, message):
    """ਫਾਈਲ ਨੂੰ ਡਾਟਾਬੇਸ ਵਿੱਚ ਆਮ ਵਾਂਗ ਸੇਵ ਕਰਦਾ ਹੈ ਅਤੇ ਚੈਨਲ ਵਿੱਚ ਸੁੰਦਰ ਪੋਸਟ ਕਰਦਾ ਹੈ"""
    # 1. ਫਾਈਲ ਨੂੰ ਪਹਿਲਾਂ ਵਾਂਗ ਡਾਟਾਬੇਸ ਵਿੱਚ ਸੇਵ ਕਰੋ
    try:
         await save_file(message)
    except Exception as e:
         print(f"Error saving to database: {e}")

    # 2. ਅਪਡੇਟ ਚੈਨਲ ਵਿੱਚ ਆਟੋਮੈਟਿਕ ਪੋਸਟ ਕਰੋ
    if not UPDATES_CHANNEL:
        return

    # ਫਾਈਲ ਦਾ ਨਾਮ ਲੱਭੋ
    file_name = None
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name or "video.mp4"

    if not file_name:
        return

    # ਫਾਈਲ ਦੀ ਜਾਣਕਾਰੀ ਪਾਰਸ ਕਰੋ
    title, year, audios, quality, is_org = parse_filename(file_name)

    # ਆਡੀਓ ਟੈਗਸ ਤਿਆਰ ਕਰੋ (Pills format ਜਿਵੇਂ #Hindi #English)
    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    full_audio_info = f"🔊 {audio_tags}{org_badge}"

    # TMDB ਪੋਸਟਰ ਲਿਆਓ
    poster = await fetch_movie_poster(title, year)
    
    # ਜੇਕਰ TMDB ਪੋਸਟਰ ਨਾ ਮਿਲੇ, ਤਾਂ ਟੈਲੀਗ੍ਰਾਮ ਫਾਈਲ ਦੇ ਆਪਣੇ ਥੰਬਨੇਲ (Thumbnail) ਦੀ ਵਰਤੋਂ ਕਰੋ
    if not poster:
        if message.video and message.video.thumbs:
            poster = message.video.thumbs[0].file_id
        elif message.document and message.document.thumbs:
            poster = message.document.thumbs[0].file_id
        else:
            # ਇੱਕ ਵਧੀਆ ਡਿਫਾਲਟ ਬੈਕਅੱਪ ਪੋਸਟਰ ਇਮੇਜ
            poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500"

    # ਤੁਹਾਡੀ ਪਸੰਦ ਦਾ ਕੈਪਸ਼ਨ ਫਾਰਮੈਟ
    caption = f"**{title} {year} (Touch To Copy)**\n\n**➥ AUDIO TRACK:-** {full_audio_info}\n\nAdded ✅"

    # ਇਨਲਾਈਨ ਗਰੁੱਪ ਲਿੰਕ ਬਟਨ
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 MOVIE REQUEST GROUP 🔰", url="https://t.me/+WtlAyRpidLExMDE1")]
    ])

    try:
        # ਅਪਡੇਟ ਚੈਨਲ ਵਿੱਚ ਸੁੰਦਰ ਪੋਸਟ ਭੇਜੋ
        await bot.send_photo(
            chat_id=UPDATES_CHANNEL,
            photo=poster,
            caption=caption,
            reply_markup=reply_markup
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await bot.send_photo(
            chat_id=UPDATES_CHANNEL,
            photo=poster,
            caption=caption,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Failed to send updates post: {e}")
