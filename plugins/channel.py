import re
import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Import the database function safely so files remain searchable in your bot
try:
    from database.ia_filterdb import save_file
except ImportError:
    try:
         from database.ia_filterdb import save_files as save_file
    except ImportError:
         # Fallback if DB structure is different
         async def save_file(*args, **kwargs):
             return True

# -------------------------------------------------------------
# Safely resolve settings from environment, info.py or config.py
# -------------------------------------------------------------
def get_config(key, default):
    # Try environment variable first
    val = os.environ.get(key)
    if val is not None:
        return val
    # Try info.py config file
    try:
        import info
        if hasattr(info, key):
            return getattr(info, key)
    except ImportError:
        pass
    # Try config.py config file
    try:
        import config
        if hasattr(config, key):
            return getattr(config, key)
    except ImportError:
        pass
    return default

# Safely resolve CHANNELS (Database Channels to look at)
raw_channels = get_config("CHANNELS", None)
if raw_channels is None:
    raw_channels = get_config("DATABASE_CHANNEL", "-1003954712996")

if isinstance(raw_channels, list):
    CHANNELS = raw_channels
elif isinstance(raw_channels, (int, float)):
    CHANNELS = [int(raw_channels)]
else:
    # Split by comma or space if it's a string
    CHANNELS = [int(v.strip()) for v in re.split(r'[,\s]+', str(raw_channels)) if v.strip().replace('-', '').replace('+', '').isdigit()]

if not CHANNELS:
    CHANNELS = [-1002427494480]

# Safely resolve UPDATES_CHANNEL (Where movie posts will be sent)
raw_updates = get_config("UPDATES_CHANNEL", get_config("LOG_CHANNEL", "-1002427494480"))
try:
    if isinstance(raw_updates, list):
        UPDATES_CHANNEL = int(raw_updates[0])
    else:
        UPDATES_CHANNEL = int(raw_updates)
except (ValueError, TypeError, IndexError):
    UPDATES_CHANNEL = -1003752618894

# Support Group values
REQUEST_GROUP_LINK = get_config("REQUEST_GROUP_LINK", "https://t.me/+WtlAyRpidLExMDE1")
REQUEST_GROUP_NAME = get_config("REQUEST_GROUP_NAME", "MOVIE REQUEST GROUP")

# TMDB Poster integration info
USE_TMDB_POSTER = str(get_config("USE_TMDB_POSTER", "True")).lower() in ("true", "1", "yes")
TMDB_API_KEY = get_config("TMDB_API_KEY", "f4e6cb562855574dff73c7801d4cebbf")

# Movie filename extraction details
QUALITY_PATTERNS = ["2160p", "1080p", "720p", "480p", "360p", "bluray", "webrip", "hdrip", "bdrip", "dvdrip"]
AUDIO_PATTERNS = {
    "hindi": "Hindi", "english": "English", "tamil": "Tamil", "telugu": "Telugu", 
    "bengali": "Bengali", "marathi": "Marathi", "kannada": "Kannada", "malayalam": "Malayalam", 
    "punjabi": "Punjabi", "dual": "Dual Audio", "multi": "Multi Audio"
}

def parse_filename(filename: str):
    # Strip extension & clean characters
    clean = re.sub(r"\.(mkv|mp4|avi|webm|mov)$", "", filename, flags=re.IGNORECASE)
    clean = re.sub(r"[\._\-]", " ", clean)

    # Detect release year
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
    year = year_match.group(1) if year_match else "2025"

    # Detect Video quality
    found_qualities = []
    clean_lower = clean.lower()
    for q in QUALITY_PATTERNS:
        if re.search(rf"\b{q}\b", clean_lower):
            found_qualities.append(q.upper())
    quality = " ".join(found_qualities) if found_qualities else "HDRip"

    # Detect Audios
    found_audios = []
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", clean_lower):
            if val not in found_audios:
                found_audios.append(val)
    if not found_audios:
        found_audios = ["Hindi"]

    # Detect Original ORG tag
    is_org = bool(re.search(r"\b(org|original)\b", clean_lower))

    # Clean Movie Title
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
    if not USE_TMDB_POSTER or not TMDB_API_KEY or TMDB_API_KEY == "f4e6cb562855574dff73c7801d4cebbf":
        return None
    search_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": title, "year": year}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results")
                    if results and results[0].get("poster_path"):
                        return f"https://image.tmdb.org/t/p/w500{results[0].get('poster_path')}"
    except Exception as e:
        print(f"Poster Fetch Error: {e}")
    return None

# Combined event listener for BOTH regular messages AND channel posts in Database Channel
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
@Client.on_channel_post(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def media(bot: Client, message: Message):
    # 1. Standard file extraction
    media_file = None
    if message.document:
        media_file = message.document
    elif message.video:
        media_file = message.video
    elif message.audio:
        media_file = message.audio
    
    if not media_file:
         return

    # 2. SAVE FILE TO MONGODB (Ensures files can be searched by users)
    try:
        await save_file(media_file)
    except Exception as dbe:
        print(f"File indexing error: {dbe}")

    # 3. AUTO-POSTING ENGINE
    file_name = getattr(media_file, "file_name", "movie_file.mp4") or "movie_file.mp4"
    title, year, audios, quality, is_org = parse_filename(file_name)

    # Beautify values for caption
    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    caption_text = f"**{title} {year} (Touch To Copy)**\n\n**➥ AUDIO TRACK:-** 🔊 {audio_tags}{org_badge}\n\nAdded ✅"

    # Button setup
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 MOVIE REQUEST GROUP 🔰", url="https://t.me/+WtlAyRpidLExMDE1")]
    ])

    # Try TMDB Poster, Fallback to Video file's original thumbnail
    poster = await fetch_movie_poster(title, year)
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            poster = media_file.thumbs[0].file_id
        else:
            # High-quality fallback image
            poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500&auto=format&fit=crop&q=60"

    try:
        # Publish update to Updates channel
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
         print(f"Failed to post update to channel: {e}")
