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

SESSION: Optional[aiohttp.ClientSession] = None

async def get_session() -> aiohttp.ClientSession:
    global SESSION
    if SESSION is None or SESSION.closed:
        SESSION = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50))
    return SESSION

POSTED_MOVIES = set()
MAX_CACHE_SIZE = 500
locks = defaultdict(asyncio.Lock)

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
    "hin": "Hindi", "hindi": "Hindi", "tam": "Tamil", "tamil": "Tamil",
    "kan": "Kannada", "kannada": "Kannada", "tel": "Telugu", "telugu": "Telugu",
    "mal": "Malayalam", "malayalam": "Malayalam", "eng": "English", "english": "English",
    "pun": "Punjabi", "punjabi": "Punjabi", "ben": "Bengali", "bengali": "Bengali",
    "mar": "Marathi", "marathi": "Marathi", "guj": "Gujarati", "gujarati": "Gujarati",
    "urd": "Urdu", "urdu": "Urdu", "kor": "Korean", "korean": "Korean",
    "jpn": "Japanese", "japanese": "Japanese",
}

OTT_PLATFORMS = {
    "nf": "Netflix", "netflix": "Netflix",
    "sonyliv": "SonyLiv", "sony": "SonyLiv", "sliv": "SonyLiv",
    "amzn": "Amazon Prime Video", "prime": "Amazon Prime Video", "primevideo": "Amazon Prime Video",
    "hotstar": "Disney+ Hotstar", "zee5": "Zee5", "jio": "JioHotstar", "jhs": "JioHotstar",
    "aha": "Aha", "hbo": "HBO Max", "paramount": "Paramount+", "apple": "Apple TV+", 
    "hoichoi": "Hoichoi", "sunnxt": "Sun NXT", "viki": "Viki"
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
EPISODE_CLEAN_PATTERN = re.compile(r'\b(S\d{1,2}|E\d{1,3}|Ep\d{1,3}|Episode\s*\d{1,3}|Season\s*\d{1,2}|Part\s*\d{1,2}|\d{1,2}\s*-\s*\d{1,2}|\d{1,3}\s*to\s*\d{1,3})\b', re.IGNORECASE)

MEDIA_FILTER = filters.document | filters.video | filters.audio

# ============ AI & OFFICIAL LANDSCAPE VALIDATION SYSTEM ============

async def fetch_cinemeta_ai_poster(query: str, is_series: bool = False) -> Optional[str]:
    """Cinemeta AI API ਦੀ ਵਰਤੋਂ ਕਰਕੇ ਸਿਰਫ ਅਧਿਕਾਰਤ ਅਤੇ ਅਸਲੀ ਮੂਵੀ ਬੈਕਡ੍ਰੌਪ ਲੱਭਣਾ"""
    try:
        session = await get_session()
        m_type = "series" if is_series else "movie"
        encoded_query = urllib.parse.quote(query)
        
        # ਸਹੀ ਮੂਵੀ ਮੈਟਾਡਾਟਾ ਆਈਡੀ ਲੱਭਣ ਲਈ ਖੋਜ
        search_url = f"https://v3-cinemeta.strem.io/catalog/{m_type}/top/search={encoded_query}.json"
        async with session.get(search_url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                metas = data.get("metas", [])
                if metas:
                    # ਪਹਿਲੇ ਸਭ ਤੋਂ ਸਹੀ ਮੈਚ ਦੀ ਚੋਣ ਕਰੋ
                    best_match = metas[0]
                    background = best_match.get("background")
                    
                    if background and any(x in background for x in ["images.metahub.space", "tmdb", "themoviedb"]):
                        logger.info(f"🤖 AI Verified Official Backdrop: {background}")
                        return background
    except Exception as e:
        logger.error(f"Cinemeta AI Metadata Error: {e}")
    return None

async def get_landscape_poster_only(movie_name: str, is_series: bool = False) -> Optional[str]:
    """ਸਿਰਫ਼ ਅਤੇ ਸਿਰਫ਼ ਅਸਲੀ ਲੈਂਡਸਕੇਪ ਪੋਸਟਰ ਕੱਢੇਗਾ, ਫਾਲਤੂ ਤਸਵੀਰਾਂ ਬਿਲਕੁਲ ਬੰਦ"""
    # 1. ਪਹਿਲਾਂ TMDB ਤੋਂ ਅਸਲੀ ਬੈਕਡ੍ਰੌਪ ਚੈੱਕ ਕਰੋ
    if LANDSCAPE_POSTER:
        try:
            details = await get_movie_detailsx(movie_name)
            if details and details.get('backdrop_url'):
                backdrop = details['backdrop_url']
                if "t/p/" in backdrop:
                    backdrop = re.sub(r'/t/p/w\d+/', '/t/p/original/', backdrop)
                    backdrop = re.sub(r'/t/p/w\d+x\d+/', '/t/p/original/', backdrop)
                logger.info(f"🌟 TMDB Backdrop Verified: {backdrop}")
                return backdrop
        except Exception as e:
            logger.error(f"TMDB backdrop error: {e}")
    
    # 2. ਜੇਕਰ TMDB 'ਤੇ ਨਾ ਮਿਲੇ, ਤਾਂ Cinemeta AI ਡਾਟਾਬੇਸ ਤੋਂ ਅਸਲੀ ਮੂਵੀ ਬੈਕਗ੍ਰਾਊਂਡ ਚੈੱਕ ਕਰੋ
    ai_backdrop = await fetch_cinemeta_ai_poster(movie_name, is_series)
    if ai_backdrop:
        return ai_backdrop
        
    # ਜੇਕਰ ਕੋਈ ਵੀ ਅਸਲੀ ਮੂਵੀ ਪੋਸਟਰ ਨਹੀਂ ਮਿਲਦਾ, ਤਾਂ ਕੋਈ ਰੈਂਡਮ ਚੀਜ਼ ਪੋਸਟ ਨਹੀਂ ਹੋਵੇਗੀ (None ਜਾਵੇਗਾ)
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
        logger.exception("Error processing incoming media updates")

async def process_and_send_update(bot, filename, caption):
    try:
        media_info = extract_media_info(filename, caption)
        base_name = media_info["base_name"]
        movie_key = base_name.lower()
        
        if len(POSTED_MOVIES) > MAX_CACHE_SIZE:
            POSTED_MOVIES.clear()
        
        if movie_key in POSTED_MOVIES:
            return

        async with locks[base_name]:
            if movie_key in POSTED_MOVIES:
                return
            POSTED_MOVIES.add(movie_key)
            
            try:
                await _process_with_lock(bot, filename, caption, media_info, base_name)
            finally:
                await asyncio.sleep(12)
                POSTED_MOVIES.discard(movie_key)
                
    except Exception as e:
        logger.exception(f"Processing execution failed: {e}")

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
            file_exists = any(f.get("filename") == filename for f in existing_movie.get("files", []))
            if not file_exists:
                await db.movie_updates.update_one({"_id": base_name}, {"$push": {"files": file_data}})
                await send_movie_update(bot, base_name, is_update=True)
            return

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

        # AI ਰਾਹੀਂ ਸਿਰਫ਼ ਅਸਲੀ ਲੈਂਡਸਕੇਪ ਪੋਸਟਰ ਲੱਭੇਗਾ
        is_series = (media_info["tag"] == "#SERIES")
        final_poster = await get_landscape_poster_only(base_name, is_series)
        
        rating_val = "N/A"
        if details.get("rating"):
            try:
                rating_val = f"{float(details.get('rating')):.1f}"
            except ValueError:
                pass

        year_val = details.get("year") or media_info["year"]

        movie_doc = {
            "_id": base_name,
            "files": [file_data],
            "poster_url": final_poster, # ਜੇਕਰ ਅਸਲੀ ਪੋਸਟਰ ਨਹੀਂ ਮਿਲਿਆ ਤਾਂ ਇਹ None ਹੋਵੇਗਾ
            "rating": rating_val,
            "year": year_val,
            "tag": media_info["tag"],
            "message_id": None,
            "is_posted": True
        }
        
        try:
            await db.movie_updates.insert_one(movie_doc)
            msg = await send_movie_update(bot, base_name, is_update=False)
            if msg:
                await db.movie_updates.update_one({"_id": base_name}, {"$set": {"message_id": msg.id}})
        except DuplicateKeyError:
            await db.movie_updates.update_one({"_id": base_name}, {"$push": {"files": file_data}})
            await send_movie_update(bot, base_name, is_update=True)

    except Exception as e:
        logger.error(f"Error in backend lock verification process: {e}")

# ============ SEND MOVIE UPDATE ============

async def send_movie_update(bot, base_name, is_update=False):
    try:
        movie_doc = await db.movie_updates.find_one({"_id": base_name})
        if not movie_doc:
            return None

        text = generate_movie_message(movie_doc, base_name)
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton(text='🔥 𝐉𝐎𝐈𝐍 𝐑𝐄𝐐𝐔𝐄𝐒𝐓 𝐆𝐑𝐎𝐔𝐏 ⚡', url="https://t.me/+l-EIo3NnnJAxODE9")]])
        poster_url = movie_doc.get("poster_url")

        # ਜੇਕਰ ਪੋਸਟ ਨੂੰ ਅਪਡੇਟ (Edit) ਕਰਨਾ ਹੈ
        if is_update and movie_doc.get("message_id"):
            try:
                if poster_url:
                    return await bot.edit_message_caption(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_id=movie_doc["message_id"],
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    return await bot.edit_message_text(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_id=movie_doc["message_id"],
                        text=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
            except MessageNotModified:
                return movie_doc
            except MessageIdInvalid:
                pass
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await send_movie_update(bot, base_name, is_update)

        # ਜੇਕਰ ਅਸਲੀ ਪੋਸਟਰ ਮਿਲ ਗਿਆ ਹੈ, ਤਾਂ ਹੀ ਫੋਟੋ ਮੈਸੇਜ ਜਾਵੇਗਾ
        if poster_url:
            try:
                return await bot.send_photo(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    photo=poster_url,
                    caption=text,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await send_movie_update(bot, base_name, is_update)
        else:
            # ਜੇਕਰ ਅਸਲੀ ਪੋਸਟਰ ਨਹੀਂ ਮਿਲਿਆ, ਤਾਂ ਕੋਈ ਰੈਂਡਮ ਫੋਟੋ ਨਹੀਂ, ਸਿੱਧਾ ਟੈਕਸਟ ਮੈਸੇਜ ਜਾਵੇਗਾ
            try:
                return await bot.send_message(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    text=text,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await send_movie_update(bot, base_name, is_update)
                
    except Exception as e:
        logger.error(f"Failed to push update layout: {e}")
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
    year_val = re.sub(r'[()\[\]]', '', year_val)
    
    year_str = f" ({year_val})" if year_val and year_val not in title else ""
    rating_raw = movie_doc.get("rating", "N/A")
    rating_str = f"{rating_raw}/10" if rating_raw != "N/A" else "N/A"
    
    return (
        f"🎬 <code>{title}{year_str}</code>\n"
        f"<i>📌 (Touch To Copy)</i>\n\n"
        f"⭐ IMDb: {rating_str}\n\n"
        f"➡ Audio Track:- 🔊 {language_str}\n\n"
        f"Added ✅"
)
