import re
import aiohttp
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Import the existing DB save_file function (from your bot's database engine)
from database.ia_filterdb import save_file

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

# Safely resolve CHANNELS (Database Channels)
raw_channels = get_config("CHANNELS", None)
if raw_channels is None:
    raw_channels = "-1003954712996" 

if isinstance(raw_channels, list):
    CHANNELS = raw_channels
elif isinstance(raw_channels, (int, float)):
    CHANNELS = [int(raw_channels)]
else:
    CHANNELS = [int(v.strip()) for v in re.split(r'[,\s]+', str(raw_channels)) if v.strip().replace('-', '').replace('+', '').isdigit()]

# Ensure CHANNELS is a list of integers
if not CHANNELS:
    CHANNELS = [-1002427494480]

# Safely resolve UPDATES_CHANNEL (Updates publishing channel)
raw_updates = get_config("UPDATES_CHANNEL", get_config("LOG_CHANNEL", "-1003752618894"))
try:
    if isinstance(raw_updates, list):
        UPDATES_CHANNEL = int(raw_updates[0])
    else:
        UPDATES_CHANNEL = int(raw_updates)
except (ValueError, TypeError, IndexError):
    UPDATES_CHANNEL = -1003752618894

# Safely resolve support group settings & TMDB
REQUEST_GROUP_LINK = get_config("REQUEST_GROUP_LINK", "https://t.me/+WtlAyRpidLExMDE1")
REQUEST_GROUP_NAME = get_config("REQUEST_GROUP_NAME", "MOVIE REQUEST GROUP")
USE_TMDB_POSTER = str(get_config("USE_TMDB_POSTER", "True")).lower() in ("true", "1", "yes")
TMDB_API_KEY = get_config("TMDB_API_KEY", "f4e6cb562855574dff73c7801d4cebbf")

# Filename parsing patterns
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

    # Clean Title
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

# Combined event trigger for Database Channel (CHANNELS)
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def media(bot: Client, message: Message):
    # 1. Standard file capture
    media_file = None
    file_type = None  # Local variable to dynamically assign type without crashes
    
    if message.document:
        media_file = message.document
        file_type = "document"
    elif message.video:
        media_file = message.video
        file_type = "video"
    elif message.audio:
        media_file = message.audio
        file_type = "audio"
    
    if not media_file:
        return

    # 2. SAVE FILE TO MONGODB (Database filter engine normal working)
    try:
        # Assign file_type using dynamic getattr/setattr safeguards safely
        try:
            setattr(media_file, "file_type", file_type)
        except Exception:
            pass
        await save_file(media_file)
    except Exception as dbe:
        print(f"DB Save failure: {dbe}")

    # 3. AUTO-POSTING ENGINE
    file_name = getattr(media_file, "file_name", "movie_file.mp4") or "movie_file.mp4"
    title, year, audios, quality, is_org = parse_filename(file_name)

    # Format texts
    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    caption_text = f"**{title} {year} (Touch To Copy)**\n\n**➥ AUDIO TRACK:-** 🔊 {audio_tags}{org_badge}\n\nAdded ✅"

    # Button setup
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 MOVIE REQUEST GROUP 🔰", url="https://t.me/+WtlAyRpidLExMDE1")]
    ])

    # Try TMDB Lookup, Fallback to downloading File Thumbnail (Avoids Expected PHOTO error)
    poster = await fetch_movie_poster(title, year)
    downloaded_poster = False
    
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            try:
                poster = await bot.download_media(media_file.thumbs[0].file_id)
                downloaded_poster = True
            except Exception as e:
                print(f"Failed to download thumbnail: {e}")
                poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500&auto=format&fit=crop&q=60"
        else:
            # Universal fallback placeholder
            poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500&auto=format&fit=crop&q=60"

    try:
        # Publish update card to your Telegram Update channel
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
        print(f"Channel update failed: {e}")
    finally:
        # Cleanup local downloaded file if it was download_media output to save space
        if downloaded_poster and poster and os.path.exists(poster):
            try:
                os.remove(poster)
            except Exception as ce:
                print(f"Error cleaning up local poster file: {ce}")
