import re
import logging
import asyncio
import aiohttp
from datetime import datetime
from collections import defaultdict
import urllib.parse
from typing import Optional, Tuple, Dict, List
from bs4 import BeautifulSoup

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageIdInvalid, MessageNotModified, FloodWait
from pymongo.errors import PyMongoError, DuplicateKeyError

# Plugin & Database Imports
from plugins.Dreamxfutures.Imdbposter import get_movie_detailsx, fetch_image, get_movie_details
from database.users_chats_db import db
from database.ia_filterdb import save_file
from utils import temp
from Script import script
from info import (
    CHANNELS, MOVIE_UPDATE_CHANNEL, LINK_PREVIEW, ABOVE_PREVIEW, 
    BAD_WORDS, LANDSCAPE_POSTER, TMDB_POSTER, NOR_IMG, IMDB_TEMPLATE
)

logger = logging.getLogger(__name__)

# Cache for posted movies
POSTED_MOVIES = set()
MAX_CACHE_SIZE = 500

IGNORE_WORDS = {
    "rarbg", "dub", "sub", "sample", "mkv", "aac", "combined", "mp4", "avi",
    "action", "adventure", "animation", "biography", "comedy", "crime", 
    "documentary", "drama", "fantasy", "film-noir", "history", 
    "horror", "music", "musical", "mystery", "romance", "sci-fi", "sport", 
    "thriller", "war", "western", "hdcam", "hdtc", "camrip", "ts", "tc", 
    "telesync", "dvdscr", "dvdrip", "predvd", "webrip", "web-dl", "tvrip", 
    "hdtv", "web dl", "webdl", "bluray", "brrip", "bdrip", "360p", "480p", 
    "720p", "1080p", "2160p", "4k", "1440p", "540p", "240p", "140p", "hevc", 
    "hdrip", "hin", "hindi", "tam", "tamil", "kan", "kannada", "tel", "telugu", 
    "mal", "malayalam", "eng", "english", "pun", "punjabi", "ben", "bengali", 
    "mar", "marathi", "guj", "gujarati", "urd", "urdu", "kor", "korean", "jpn", 
    "japanese", "nf", "netflix", "sonyliv", "sony", "sliv", "amzn", "prime", 
    "primevideo", "hotstar", "zee5", "jio", "jiohotstar", "jhs", "aha", "hbo", "paramount", 
    "apple", "hoichoi", "sunnxt", "viki", "x264", "x265", "avc", "dd5", "dovi", "hdr"
} | BAD_WORDS

CAPTION_LANGUAGES = {
    "hin": "Hindi", "hindi": "Hindi",
    "tam": "Tamil", "tamil": "Tamil",
    "kan": "Kannada", "kannada": "Kannada",
    "tel": "Telugu", "telugu": "Telugu",
    "mal": "Malayalam", "malayalam": "Malayalam",
    "eng": "English", "english": "English",
    "pun": "Punjabi", "punjabi": "Punjabi",
    "ben": "Bengali", "bengali": "Bengali",
    "mar": "Marathi", "marathi": "Marathi",
    "guj": "Gujarati", "gujarati": "Gujarati",
    "urd": "Urdu", "urdu": "Urdu",
    "kor": "Korean", "korean": "Korean",
    "jpn": "Japanese", "japanese": "Japanese",
}

OTT_PLATFORMS = {
    "nf": "Netflix", "netflix": "Netflix",
    "sonyliv": "SonyLiv", "sony": "SonyLiv", "sliv": "SonyLiv",
    "amzn": "Amazon Prime Video", "prime": "Amazon Prime Video", "primevideo": "Amazon Prime Video",
    "hotstar": "Disney+ Hotstar", "zee5": "Zee5",
    "jio": "JioHotstar", "jhs": "JioHotstar",
    "aha": "Aha", "hbo": "HBO Max", "paramount": "Paramount+",
    "apple": "Apple TV+", "hoichoi": "Hoichoi", "sunnxt": "Sun NXT", "viki": "Viki"
}

STANDARD_GENRES = {
    'Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime', 'Documentary',
    'Drama', 'Family', 'Fantasy', 'Film-Noir', 'History', 'Horror', 'Music',
    'Musical', 'Mystery', 'Romance', 'Sci-Fi', 'Sport', 'Thriller', 'War', 'Western'
}

CLEAN_PATTERN = re.compile(r'@[^ \n\r\t\.,:;!?()\[\]{}<>\\/"\'=_%]+|\bwww\.[^\s\]\)]+|\([\@^]+\)|\[[\@^]+\]')
NORMALIZE_PATTERN = re.compile(r"[._\-\+]+|[()\[\]{}:;'–!,.?]")
QUALITY_PATTERN = re.compile(
    r"\b(?:HDCam|HDTC|CamRip|TS|TC|TeleSync|DVDScr|DVDRip|PreDVD|"
    r"WEBRip|WEB-DL|TVRip|HDTV|WEB DL|WebDl|BluRay|BRRip|BDRip|"
    r"360p|480p|720p|1080p|2160p|4K|1440p|540p|240p|140p|HEVC|HDRip|x264|x265)\b", 
    re.IGNORECASE
)
YEAR_PATTERN = re.compile(r"(?<![A-Za-z0-9])(19\d{2}|20\d{2})(?![A-Za-z0-9])")

# ਐਪੀਸੋਡ ਅਤੇ ਸੀਜ਼ਨ ਫਿਲਟਰ ਕਰਨ ਲਈ ਪੈਟਰਨ
EPISODE_CLEAN_PATTERN = re.compile(r'\b(S\d{1,2}|E\d{1,3}|Ep\d{1,3}|Episode\s*\d{1,3}|Season\s*\d{1,2}|Part\s*\d{1,2}|\d{1,2}\s*-\s*\d{1,2}|\d{1,3}\s*to\s*\d{1,3})\b', re.IGNORECASE)

MEDIA_FILTER = filters.document | filters.video | filters.audio
locks = defaultdict(asyncio.Lock)

# ============ ADVANCED HD LANDSCAPE POSTER GENERATOR ============

class LandscapePosterGenerator:
    """ਤੁਹਾਡੀ ਪਸੰਦ ਮੁਤਾਬਕ ਪੋਸਟਰ ਦੇ ਹੇਠਾਂ ਫਿਲਮ ਦਾ ਨਾਮ ਲਿਖ ਕੇ HD ਲੈਂਡਸਕੇਪ ਪੋਸਟਰ ਤਿਆਰ ਕਰਦਾ ਹੈ"""
    @staticmethod
    async def generate_landscape(vertical_poster_url: str, movie_name: str = "") -> Optional[str]:
        try:
            if not vertical_poster_url:
                return None
            
            if "t/p/" in vertical_poster_url:
                vertical_poster_url = re.sub(r'/t/p/w\d+/', '/t/p/original/', vertical_poster_url)
                vertical_poster_url = re.sub(r'/t/p/w\d+x\d+/', '/t/p/original/', vertical_poster_url)
            
            encoded_url = urllib.parse.quote_plus(vertical_poster_url)
            display_title = urllib.parse.quote_plus(movie_name.upper())
            
            # Weserv API ਦੀ ਵਰਤੋਂ ਕਰਕੇ ਬੈਕਗ੍ਰਾਊਂਡ ਬਲਰ ਕੀਤਾ ਅਤੇ ਥੱਲੇ ਫਿਲਮ ਦਾ ਨਾਮ ਲਿਖਿਆ
            landscape_url = (
                f"https://images.weserv.nl/"
                f"?url={encoded_url}"
                f"&w=1280&h=720"
                f"&fit=contain"
                f"&cbg=blur&blur=12"
                f"&border=4&bcol=ffffff"
                f"&a=c&q=100&output=jpg"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.head(landscape_url, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"✅ HD Widescreen Blurred Poster generated for: {movie_name}")
                        return landscape_url
                    else:
                        return vertical_poster_url
                    
        except Exception as e:
            logger.error(f"❌ Error generating advanced landscape: {e}")
            return vertical_poster_url

# ============ POSTER FETCHING FUNCTIONS ============

async def fetch_free_landscape_poster(query: str) -> Optional[str]:
    try:
        search_url = "https://html.duckduckgo.com/html/"
        payload = {'q': f"{query} movie hd widescreen backdrop wallpaper"}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(search_url, data=payload, headers=headers, timeout=10) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    images = soup.find_all('img', class_='image-thumb') or soup.find_all('img')
                    for img in images:
                        src = img.get('src', '')
                        if "duckduckgo.com/iu/?u=" in src:
                            actual_url = src.split('?u=')[1].split('&')[0]
                            actual_url = urllib.parse.unquote(actual_url)
                            if any(ext in actual_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                async with session.head(actual_url, timeout=10) as resp:
                                    if resp.status == 200 and 'image' in resp.headers.get('content-type', ''):
                                        return actual_url
    except Exception as e:
        logger.error(f"Free Scraping Search Error: {e}")
    return None

async def get_landscape_poster_only(movie_name: str, vertical_poster: Optional[str] = None) -> Optional[str]:
    # ਪਹਿਲਾਂ TMDB ਤੋਂ ਲੈਂਡਸਕੇਪ (Backdrop) ਲੱਭੋ
    if LANDSCAPE_POSTER:
        try:
            details = await get_movie_detailsx(movie_name)
            if details and details.get('backdrop_url'):
                backdrop = details['backdrop_url']
                if "t/p/" in backdrop:
                    backdrop = re.sub(r'/t/p/w\d+/', '/t/p/original/', backdrop)
                return backdrop
        except Exception as e:
            logger.error(f"TMDB backdrop error: {e}")
    
    # ਜੇਕਰ TMDB ਤੋਂ ਨਾ ਮਿਲੇ, ਤਾਂ ਗੂਗਲ/ਡੱਕਡੱਕਗੋ ਤੋਂ ਅਸਲੀ ਵਾਈਡਸਕ੍ਰੀਨ ਇਮੇਜ ਲੱਭੋ
    landscape = await fetch_free_landscape_poster(movie_name)
    if landscape:
        return landscape
    
    # ਜੇਕਰ ਕੁਝ ਵੀ ਨਾ ਮਿਲੇ, ਤਾਂ ਵਰਟੀਕਲ ਪੋਸਟਰ ਨੂੰ ਖੂਬਸੂਰਤ HD ਬਲਰ ਲੈਂਡਸਕੇਪ ਵਿੱਚ ਬਦਲੋ
    if vertical_poster:
        generator = LandscapePosterGenerator()
        return await generator.generate_landscape(vertical_poster, movie_name)
    
    return None

# ============ CLEANING AND EXTRACTION FUNCTIONS ============

def clean_mentions_links(text: str) -> str:
    return CLEAN_PATTERN.sub("", text or "").strip()

def normalize(s: str) -> str:
    s = NORMALIZE_PATTERN.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()

def remove_ignored_words(text: str) -> str:
    IGNORE_WORDS_LOWER = {w.lower() for w in IGNORE_WORDS}
    words = text.split()
    cleaned_words = []
    for word in words:
        if word.lower() in IGNORE_WORDS_LOWER:
            break
        cleaned_words.append(word)
    return " ".join(cleaned_words)

def extract_media_info(filename: str, caption: str):
    filename_cleaned = clean_mentions_links(filename)
    filename_normalized = normalize(filename_cleaned)
    caption_clean = clean_mentions_links(caption).lower() if caption else ""

    tag = "#MOVIE"
    year = None
    
    quality = QUALITY_PATTERN.findall(filename_normalized)
    quality_str = ", ".join(quality) if quality else "N/A"
    ott_platform = extract_ott_platform(f"{filename_normalized} {caption_clean}")

    lang_keys = {k for k in CAPTION_LANGUAGES if k in caption_clean or k in filename_normalized.lower()}
    language = ", ".join(sorted({CAPTION_LANGUAGES[k] for k in lang_keys})) if lang_keys else "N/A"

    # ਐਪੀਸੋਡ ਅਤੇ ਸੀਜ਼ਨ ਦੇ ਟੈਗਸ ਨੂੰ ਨਾਮ ਵਿੱਚੋਂ ਪੂਰੀ ਤਰ੍ਹਾਂ ਹਟਾਉਣਾ ਤਾਂ ਜੋ ਸਿੰਗਲ ਪੋਸਟ ਬਣੇ
    if EPISODE_CLEAN_PATTERN.search(filename_normalized):
        tag = "#SERIES"
    
    clean_name = EPISODE_CLEAN_PATTERN.sub(" ", filename_normalized)

    year_match = YEAR_PATTERN.search(clean_name)
    if year_match:
        year = year_match.group(1)
        idx = clean_name.find(year)
        base_raw = clean_name[:idx].strip()
    else:
        qual_match = QUALITY_PATTERN.search(clean_name)
        if qual_match:
            idx = clean_name.lower().find(qual_match.group(0).lower())
            base_raw = clean_name[:idx].strip()
        else:
            base_raw = clean_name

    base_name = normalize(remove_ignored_words(base_raw))
    if not base_name:
        base_name = filename_normalized

    return {
        "processed": filename_normalized,
        "base_name": base_name.title(),
        "tag": tag,
        "year": year,
        "quality": quality_str,
        "ott_platform": ott_platform,
        "language": language
    }

def extract_ott_platform(text: str) -> str:
    text = text.lower()
    platforms = {plat for key, plat in OTT_PLATFORMS.items() if key in text}
    return " | ".join(platforms) if platforms else "N/A"

# ============ MAIN HANDLERS ============

@Client.on_message(filters.chat(CHANNELS) & MEDIA_FILTER)
async def media_handler(bot, message):
    media = next((getattr(message, ft) for ft in ("document", "video", "audio") if getattr(message, ft, None)), None)
    if not media:
        return

    media.file_type = next(ft for ft in ("document", "video", "audio") if hasattr(message, ft))
    media.caption = message.caption or ""
    
    success, info = await save_file(media)
    if not success:
        return

    try:
        if await db.movie_update_status(bot.me.id):
            await process_and_send_update(bot, media.file_name, media.caption)
    except Exception:
        logger.exception("Error processing media")

async def process_and_send_update(bot, filename, caption):
    try:
        media_info = extract_media_info(filename, caption)
        base_name = media_info["base_name"]

        movie_key = f"{base_name.lower()}"
        
        if len(POSTED_MOVIES) > MAX_CACHE_SIZE:
            POSTED_MOVIES.clear()
        
        if movie_key in POSTED_MOVIES:
            return

        lock = locks[base_name]
        async with lock:
            if movie_key in POSTED_MOVIES:
                return
            POSTED_MOVIES.add(movie_key)
            await _process_with_lock(bot, filename, caption, media_info, base_name)
            
            await asyncio.sleep(10)
            POSTED_MOVIES.discard(movie_key)

    except Exception as e:
        logger.exception(f"Processing failed: {e}")

# ============ PROCESS WITH LOCK ============

async def _process_with_lock(bot, filename, caption, media_info, base_name):
    if not hasattr(db, 'movie_updates'):
        db.movie_updates = db.db.movie_updates

    error_tmdb = False
    
    file_data = {
        "filename": filename,
        "quality": media_info["quality"],
        "language": media_info["language"],
        "timestamp": datetime.now()
    }

    try:
        existing_movie = await db.movie_updates.find_one({"_id": base_name})
        
        if existing_movie:
            # ਸਾਲ ਦੀ ਰੇਂਜ ਬਣਾਉਣਾ ਅਤੇ ਡਬਲ ਸਾਲ ਠੀਕ ਕਰਨਾ
            new_year = media_info["year"]
            old_year = existing_movie.get("year")
            
            if new_year and old_year and str(new_year) != str(old_year):
                # ਸਾਲਾਂ ਨੂੰ ਸਾਫ਼ ਕਰਕੇ Range ਸੈੱਟ ਕਰਨਾ
                clean_old = re.sub(r'[() \s]', '', str(old_year))
                if "-" in clean_old:
                    start_yr = clean_old.split("-")[0].strip()
                    if int(new_year) > int(start_yr):
                        await db.movie_updates.update_one({"_id": base_name}, {"$set": {"year": f"{start_yr} - {new_year}"}})
                else:
                    if int(new_year) > int(clean_old):
                        await db.movie_updates.update_one({"_id": base_name}, {"$set": {"year": f"{clean_old} - {new_year}"}})
                    elif int(new_year) < int(clean_old):
                        await db.movie_updates.update_one({"_id": base_name}, {"$set": {"year": f"{new_year} - {clean_old}"}})

            file_exists = any(f.get("filename") == filename for f in existing_movie.get("files", []))
            if not file_exists:
                await db.movie_updates.update_one({"_id": base_name}, {"$push": {"files": file_data}})
                await send_movie_update(bot, base_name, is_update=True)
            return

        # NEW MOVIE / SERIES
        details = {}
        if TMDB_POSTER:
            try:
                details = await get_movie_detailsx(base_name)
                if not details or details.get("error"):
                    error_tmdb = True
            except Exception:
                error_tmdb = True
                
        if not TMDB_POSTER or error_tmdb or not details:
            details = await get_movie_details(base_name) or {}

        final_poster = await get_landscape_poster_only(base_name, details.get("poster_url"))
        
        rating_val = "N/A"
        if details.get("rating"):
            try:
                rating_val = f"{float(details.get('rating')):.1f}"
            except ValueError:
                pass

        tmdb_year = details.get("year")
        file_year = media_info["year"]
        year_val = f"{tmdb_year} - {file_year}" if tmdb_year and file_year and str(tmdb_year) != str(file_year) else (tmdb_year or file_year)

        movie_doc = {
            "_id": base_name,
            "files": [file_data],
            "poster_url": final_poster,
            "rating": rating_val,
            "year": year_val,
            "tag": media_info["tag"],
            "message_id": None,
            "is_posted": final_poster is not None
        }
        
        await db.movie_updates.insert_one(movie_doc)
        
        if final_poster:
            msg = await send_movie_update(bot, base_name, is_update=False)
            if msg:
                await db.movie_updates.update_one({"_id": base_name}, {"$set": {"message_id": msg.id}})

    except DuplicateKeyError:
        await db.movie_updates.update_one({"_id": base_name}, {"$push": {"files": file_data}})
        await send_movie_update(bot, base_name, is_update=True)
    except Exception as e:
        logger.error(f"Error in lock process: {e}")

# ============ SEND MOVIE UPDATE ============

async def send_movie_update(bot, base_name, is_update=False):
    try:
        movie_doc = await db.movie_updates.find_one({"_id": base_name})
        if not movie_doc:
            return None

        text = generate_movie_message(movie_doc, base_name)
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton(text='🔥 𝐉𝐎𝐈𝐍 𝐑𝐄𝐐𝐔𝐄𝐒𝐓 𝐆𝐑𝐎𝐔𝐏 ⚡', url="https://t.me/+l-EIo3NnnJAxODE9")]])
        poster_url = movie_doc.get("poster_url")

        if is_update and movie_doc.get("message_id"):
            try:
                return await bot.edit_message_caption(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    message_id=movie_doc["message_id"],
                    caption=text,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except MessageNotModified:
                return movie_doc
            except MessageIdInvalid:
                pass

        if poster_url:
            msg = await bot.send_photo(
                chat_id=MOVIE_UPDATE_CHANNEL,
                photo=poster_url,
                caption=text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML
            )
            return msg
    except Exception as e:
        logger.error(f"Failed to send update: {e}")
    return None

# ============ GENERATE MOVIE MESSAGE ============

def generate_movie_message(movie_doc, base_name) -> str:
    all_languages = set()
    for file in movie_doc["files"]:
        if file.get("language") and file["language"] != "N/A":
            all_languages.update(l.strip() for l in file["language"].split(",") if l.strip())
    
    language_str = " ".join(f"#{lang}" for lang in sorted(all_languages)) if all_languages else "#Hindi"
    
    title = base_name.upper()
    year_val = str(movie_doc.get("year", "")).strip()
    
    # ਕਿਸੇ ਵੀ ਤਰ੍ਹਾਂ ਦੇ ਫਾਲਤੂ ਬਰੈਕਟਾਂ ਨੂੰ ਹਟਾਉਣਾ ਅਤੇ ਸਾਫ਼ ਰੇਂਜ ਬਣਾਉਣਾ
    year_val = re.sub(r'[()\[\]]', '', year_val)
    
    if year_val and year_val not in title:
        year_str = f" ({year_val})"
    else:
        year_str = ""
    
    rating_raw = movie_doc.get("rating", "N/A")
    rating_str = f"{rating_raw}/10" if rating_raw != "N/A" else "N/A"
    
    message = (
        f"🎬 {title}{year_str}\n\n"
        f"⭐ IMDb: {rating_str}\n\n"
        f"➡ Audio Track:- 🔊 {language_str}\n\n"
        f"Added ✅"
    )
    return message
