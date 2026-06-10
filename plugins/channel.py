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
    # Fallback to direct import based on your repo structure
    try:
        from database.ia_filterdb import Alpha as save_file
    except ImportError:
        def save_file(*args, **kwargs):
            pass

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

# Safely resolve Database Channels (where you forward files)
raw_channels = get_config("CHANNELS", None)
if isinstance(raw_channels, list):
    CHANNELS = raw_channels
elif isinstance(raw_channels, (int, float)):
    CHANNELS = [int(raw_channels)]
else:
    # Extract multiple IDs separated by spaces/commas
    CHANNELS = [int(v.strip()) for v in re.split(r'[,\s]+', str(raw_channels)) if v.strip().replace('-', '').replace('+', '').isdigit()]

if not CHANNELS:
    CHANNELS = [-1003954712996] # Replace with your Database Channel ID in .env / info.py

# Safely resolve Updates posting channel
raw_updates = get_config("UPDATES_CHANNEL", get_config("LOG_CHANNEL", "-1003752618894"))
try:
    if isinstance(raw_updates, list):
        UPDATES_CHANNEL = int(raw_updates[0])
    else:
        UPDATES_CHANNEL = int(raw_updates)
except (ValueError, TypeError, IndexError):
    UPDATES_CHANNEL = -1003752618894 # Replace with your Main Updates Channel ID

# Configuration options
REQUEST_GROUP_LINK = get_config("REQUEST_GROUP_LINK", "https://t.me/+WtlAyRpidLExMDE1")
REQUEST_GROUP_NAME = get_config("REQUEST_GROUP_NAME", "PROJECT GROUP")
USE_TMDB_POSTER = str(get_config("USE_TMDB_POSTER", "True")).lower() in ("true", "1", "yes")
TMDB_API_KEY = get_config("TMDB_API_KEY", "db55323b8d3e4154498498a75642b381")

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
    """
    Parses filenames and automatically strips Telegram promotion tags, channel links,
    and brackets (e.g., [@ClipmateZone]) so TMDb search gets a perfectly clean title.
    """
    clean = str(filename)
    
    # 1. Clean bracketed channel names or usernames (e.g. [@ClipmateZone])
    clean = re.sub(r"\[\s*@?[\w_]+\s*\]", " ", clean, flags=re.IGNORECASE)
    
    # 2. Clean bracketed or parenthesized t.me links (e.g. [t.me/ClipmateZone])
    clean = re.sub(r"\[\s*(https?://)?(t\.me|telegram\.me)/[\w_]+\s*\]", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\(\s*(https?://)?(t\.me|telegram\.me)/[\w_]+\s*\)", " ", clean, flags=re.IGNORECASE)
    
    # 3. Clean standalone telegram URLs (e.g. t.me/ClipmateZone)
    clean = re.sub(r"\b(https?://)?(t\.me|telegram\.me)/[\w_]+\b", " ", clean, flags=re.IGNORECASE)
    
    # 4. Clean standalone @usernames
    clean = re.sub(r"@[\w_]+", " ", clean)

    # Remove standard video file extensions
    clean = re.sub(r"\.(mkv|mp4|avi|webm|mov|3gp)$", "", clean, flags=re.IGNORECASE)
    
    # Replace dividers (dots, underscores, dashes) with spaces
    clean = re.sub(r"[\._\-]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()

    # Detect Year (4-digit number like 19xx or 20xx)
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", clean)
    year = year_match.group(1) if year_match else "2026"

    # Detect Video quality
    found_qualities = []
    clean_lower = clean.lower()
    for q in QUALITY_PATTERNS:
        if re.search(rf"\b{q}\b", clean_lower):
            found_qualities.append(q.upper())
    quality = " ".join(found_qualities) if found_qualities else "HDRip"

    # Detect Audio Tracks
    found_audios = []
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", clean_lower):
            if val not in found_audios:
                found_audios.append(val)
    if not found_audios:
        found_audios = ["Hindi"]

    # Detect if Original Audio
    is_org = bool(re.search(r"\b(org|original)\b", clean_lower))

    # Determine Title by cutting everything after the Year or Quality tag
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
    """
    Fetches the highest quality Movie Poster. 
    Flow: TMDB API -> iTunes API Fallback (Awesome and Free) -> TVMaze API Fallback (Shows/Anime) -> None.
    """
    # 1. TMDB Search (Requires API Key)
    if USE_TMDB_POSTER and TMDB_API_KEY and TMDB_API_KEY != "db55323b8d3e4154498498a75642b381":
        try:
            search_url = "https://api.themoviedb.org/3/search/movie"
            params = {"api_key": TMDB_API_KEY, "query": title, "year": year}
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, timeout=5) as r:
                    if r.status == 200:
                        data = await r.json()
                        results = data.get("results")
                        if movie.get('backdrop_path'):
                           poster = f"https://image.tmdb.org/t/p/w1280{movie.get('backdrop_path')}"
                    elif movie.get('poster_path'):
                        poster = f"https://image.tmdb.org/t/p/w1280{movie.get('poster_path')}"
                    else:
                        poster = None
        except Exception as e:
            print(f"TMDb Poster Search Error: {e}")

    # 2. iTunes Movie Search (Free & Unlimited, No Key Needed, High Resolution!)
    try:
        search_query = f"{title} {year}".strip()
        itunes_url = "https://itunes.apple.com/search"
        params = {"term": search_query, "entity": "movie", "limit": 1}
        async with aiohttp.ClientSession() as session:
            async with session.get(itunes_url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results")
                    if results and results[0].get("artworkUrl100"):
                        artwork_url = results[0].get("artworkUrl100")
                        # High-resolution conversion
                        return artwork_url.replace("100x100bb.jpg", "1000x1000bb.jpg").replace("100x100", "1000x1000")
    except Exception as e:
        print(f"iTunes Poster Fallback Error: {e}")

    # 3. iTunes Show/Anime search (if movie filter failed)
    try:
        itunes_url = "https://itunes.apple.com/search"
        params = {"term": title, "limit": 1}
        async with aiohttp.ClientSession() as session:
            async with session.get(itunes_url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results")
                    if results and results[0].get("artworkUrl100"):
                        artwork_url = results[0].get("artworkUrl100")
                        return artwork_url.replace("100x100bb.jpg", "1000x1000bb.jpg").replace("100x100", "1000x1000")
    except Exception as e:
        print(f"iTunes General Fallback Error: {e}")

    # 4. TVMaze API (Best for webseries and TV shows)
    try:
        tvmaze_url = "https://api.tvmaze.com/singlesearch/shows"
        params = {"q": title}
        async with aiohttp.ClientSession() as session:
            async with session.get(tvmaze_url, params=params, timeout=5) as r:
                if r.status == 200:
                    data = await r.json()
                    if data and data.get("image"):
                        img = data.get("image")
                        return img.get("original") or img.get("medium")
    except Exception as e:
        print(f"TVMaze Poster Fallback Error: {e}")

    return None

# Trigger when media is uploaded/forwarded to Database Channels
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

    # 1. Save file to MariaDB / MongoDB (keeps your search system indexed)
    try:
        await save_file(media_file)
    except Exception as dbe:
        print(f"DB Save failure (Normal if indexing logic differs): {dbe}")

    # 2. Parse cleansed metadata
    file_name = getattr(media_file, "file_name", "movie_file.mp4") or "movie_file.mp4"
    title, year, audios, quality, is_org = parse_filename(file_name)

    # Format Telegram post elements
    audio_tags = " ".join([f"#{lang}" for lang in audios])
    org_badge = " #ORG" if is_org else ""
    
    # Custom post caption
    caption_text = f"**{title} {year} (Touch To Copy)**\n\n**➥ AUDIO TRACK:-** 🔊 {audio_tags}{org_badge}\n\nAdded ✅"

    # Setup Request channel buttons
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(text=f"🔰 MOVIE REQUEST GROUP 🔰", url="https://t.me/+WtlAyRpidLExMDE1")]
    ])

    # Find HD poster image
    poster = await fetch_movie_poster(title, year)
    
    # Fallback to file's default telegram thumbnail if TMDb/iTunes found absolutely nothing
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            try:
                poster = await bot.download_media(media_file.thumbs[0].file_id)
            except Exception:
                poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500"
        else:
            poster = "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=500"

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
        print(f"Channel update failed to send photo: {e}")
    finally:
        # If photo was downloaded locally, clean it up!
        if poster and not poster.startswith("http") and os.path.exists(poster):
            try:
                os.remove(poster)
            except Exception:
                pass
