import re
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Import the existing DB save_file function (from your bot's database engine)
from database.ia_filterdb import save_file

# Import config constants
try:
    from info import CHANNELS, UPDATES_CHANNEL, REQUEST_GROUP_LINK, REQUEST_GROUP_NAME, USE_TMDB_POSTER, TMDB_API_KEY
except ImportError:
    try:
        from config import CHANNELS, UPDATES_CHANNEL, REQUEST_GROUP_LINK, REQUEST_GROUP_NAME, USE_TMDB_POSTER, TMDB_API_KEY
    except ImportError:
        # Fallback values if imports fail
        CHANNELS = [-1002239262549] # Replace with database channel lists
        UPDATES_CHANNEL = -1002537474111 # Replace with your updates channel ID
        REQUEST_GROUP_LINK = "https://t.me/+WtlAyRpidLExMDE1"
        REQUEST_GROUP_NAME = "MOVIE REQUEST GROUP"
        USE_TMDB_POSTER = False
        TMDB_API_KEY = "YOUR_TMDB_API_KEY"

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
    if not USE_TMDB_POSTER or TMDB_API_KEY == "YOUR_TMDB_API_KEY" or not TMDB_API_KEY:
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
@Client.on_message(filters.chat(CHANNELS) & filters.incoming)
async def media(bot: Client, message: Message):
    # 1. Standard file capture
    media_file = None
    if message.document:
        media_file = message.document
    elif message.video:
        media_file = message.video
    elif message.audio:
        media_file = message.audio
    
    if not media_file:
        return

    # 2. SAVE FILE TO MONGODB (Keeps indexer working normally)
    try:
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

    # Try TMDB Lookup, Fallback to File Thumbnail
    poster = await fetch_movie_poster(title, year)
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            poster = media_file.thumbs[0].file_id
        else:
            # Universal fallback placeholder
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
        print(f"Channel update failed: {e}")
