import re
import logging
import asyncio
import aiohttp
import html
import io
import textwrap
from datetime import datetime
from collections import defaultdict
import urllib.parse
from typing import Optional, Tuple, Dict, List
from bs4 import BeautifulSoup

# Pillow (PIL) for image editing
from PIL import Image, ImageDraw, ImageFont

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
    BAD_WORDS, LANDSCAPE_POSTER, TMDB_POSTER, NOR_IMG, IMDB_TEMPLATE,
    TMDB_API_KEY  # ✅ API Key info.py ਤੋਂ import ਕੀਤੀ
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
    "apple", "hoichoi", "sunnxt", "viki", "x264", "x265", "avc", "dd5", "dovi", "hdr",
    "10bit", "10-bit", "8bit", "8-bit"
} | BAD_WORDS

# ============ TMDB LANGUAGE CODE TO FULL NAME MAPPING ============
TMDB_LANG_MAP = {
    "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam",
    "kn": "Kannada", "en": "English", "bn": "Bengali", "mr": "Marathi",
    "gu": "Gujarati", "pa": "Punjabi", "ur": "Urdu", "ko": "Korean",
    "ja": "Japanese", "es": "Spanish", "fr": "French", "de": "German",
    "zh": "Chinese", "ru": "Russian", "it": "Italian", "pt": "Portuguese",
    "ar": "Arabic", "nl": "Dutch", "sv": "Swedish", "pl": "Polish",
    "vi": "Vietnamese", "th": "Thai", "id": "Indonesian", "ms": "Malay",
    "tr": "Turkish", "el": "Greek", "he": "Hebrew", "cs": "Czech",
    "da": "Danish", "fi": "Finnish", "hu": "Hungarian", "no": "Norwegian",
    "ro": "Romanian", "sk": "Slovak", "sl": "Slovenian", "hr": "Croatian",
}

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
    r"360p|480p|720p|1080p|2160p|4K|1440p|540p|240p|140p|HEVC|HDRip|x264|x265|10bit|10-bit|8bit)\b", 
    re.IGNORECASE
)
YEAR_PATTERN = re.compile(r"(?<![A-Za-z0-9])(19\d{2}|20\d{2})(?![A-Za-z0-9])")
EPISODE_CLEAN_PATTERN = re.compile(r'\b(S\d{1,2}|E\d{1,3}|Ep\d{1,3}|Episode\s*\d{1,3}|Season\s*\d{1,2}|Part\s*\d{1,2}|\d{1,2}\s*-\s*\d{1,2}|\d{1,3}\s*to\s*\d{1,3})\b', re.IGNORECASE)

# ============ LANGUAGE EXTRACTION WITH REGEX WORD BOUNDARIES ============
LANG_PATTERN = re.compile(
    r'\b(?:hin|hindi|tam|tamil|kan|kannada|tel|telugu|mal|malayalam|'
    r'eng|english|pun|punjabi|ben|bengali|mar|marathi|guj|gujarati|'
    r'urd|urdu|kor|korean|jpn|japanese)\b',
    re.IGNORECASE
)

MEDIA_FILTER = filters.document | filters.video | filters.audio

# ============ NEW: CREATE TITLE-ONLY POSTER ============

async def create_title_only_poster(backdrop_url: str, title: str) -> Optional[bytes]:
    """
    backdrop_url ਤੋਂ ਇਮੇਜ ਡਾਊਨਲੋਡ ਕਰੋ, ਉਸ 'ਤੇ ਸਿਰਫ਼ ਟਾਈਟਲ (ਵੱਡਾ, ਚਿੱਟਾ, ਸੈਂਟਰਡ) ਲਿਖੋ।
    ਜੇਕਰ backdrop ਨਾ ਮਿਲੇ, ਤਾਂ None ਵਾਪਸ ਕਰੋ।
    """
    try:
        # 1. Backdrop ਡਾਊਨਲੋਡ
        async with aiohttp.ClientSession() as session:
            async with session.get(backdrop_url) as resp:
                if resp.status != 200:
                    return None
                img_data = await resp.read()
        
        # 2. PIL Image ਖੋਲ੍ਹੋ
        image = Image.open(io.BytesIO(img_data)).convert("RGB")
        img_w, img_h = image.size
        
        # 3. Draw object
        draw = ImageDraw.Draw(image)
        
        # 4. ਫੌਂਟ ਲੋਡ ਕਰੋ (Bold, ਵੱਡਾ) - Heroku 'ਤੇ DejaVu ਉਪਲਬਧ ਹੈ
        try:
            font_size = int(img_w * 0.10)  # 10% of width
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            # Fallback to default font if not available
            font = ImageFont.load_default()
            font_size = 20  # default size
        
        # 5. ਟਾਈਟਲ ਨੂੰ wrap ਕਰੋ (ਜੇ ਬਹੁਤ ਲੰਮਾ ਹੋਵੇ)
        wrapped_title = textwrap.fill(title.upper(), width=14)  # max 14 chars per line
        
        # 6. ਟੈਕਸਟ ਦਾ size ਮਾਪੋ
        bbox = draw.textbbox((0, 0), wrapped_title, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # 7. Center coordinates
        x = (img_w - text_w) // 2
        y = (img_h - text_h) // 2 - int(text_h * 0.2)  # slightly above center
        
        # 8. ਪਿਛੋਕੜ 'ਤੇ ਅਰਧ-ਪਾਰਦਰਸ਼ੀ ਕਾਲੀ ਪੱਟੀ (rectangle) ਲਗਾਓ ਤਾਂ ਜੋ ਟੈਕਸਟ ਸਾਫ਼ ਦਿਖੇ
        padding = 25
        # For semi-transparent overlay, we need to create a separate layer, but simpler: draw black rectangle with alpha
        # PIL does not support alpha directly on RGB; we can create a new image or use rectangle with fill=(0,0,0) and then adjust opacity via Image.blend? 
        # Simpler: draw a black rectangle with opacity using ImageColor? Actually we can create a new layer:
        overlay = Image.new('RGBA', (img_w, img_h), (0,0,0,0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [x - padding, y - padding, x + text_w + padding, y + text_h + padding],
            fill=(0, 0, 0, 170)  # black with opacity 170/255
        )
        # Blend overlay onto image
        image = image.convert('RGBA')
        image = Image.alpha_composite(image, overlay)
        image = image.convert('RGB')  # back to RGB for saving
        draw = ImageDraw.Draw(image)  # recreate draw after conversion
        
        # 9. ਚਿੱਟੇ ਰੰਗ ਵਿੱਚ ਟੈਕਸਟ ਲਿਖੋ (ਇਸ ਵਾਰ overlay ਦੇ ਉੱਪਰ)
        draw.text((x, y), wrapped_title, font=font, fill=(255, 255, 255))
        
        # 10. Bytes ਵਿੱਚ ਆਊਟਪੁੱਟ
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=92)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Title-only poster generation failed: {e}")
        return None

# ============ AI & OFFICIAL LANDSCAPE VALIDATION SYSTEM ============

async def fetch_cinemeta_ai_poster(query: str, is_series: bool = False) -> Optional[str]:
    try:
        session = await get_session()
        m_type = "series" if is_series else "movie"
        encoded_query = urllib.parse.quote(query)
        
        search_url = f"https://v3-cinemeta.strem.io/catalog/{m_type}/top/search={encoded_query}.json"
        async with session.get(search_url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                metas = data.get("metas", [])
                if metas:
                    best_match = metas[0]
                    background = best_match.get("background")
                    if background and any(x in background for x in ["images.metahub.space", "tmdb", "themoviedb"]):
                        return background
    except Exception as e:
        logger.error(f"Cinemeta AI Metadata Error: {e}")
    return None

async def get_landscape_poster_only(movie_name: str, is_series: bool = False) -> Optional[str]:
    if LANDSCAPE_POSTER:
        try:
            details = await get_movie_detailsx(movie_name)
            if details and details.get('backdrop_url'):
                backdrop = details['backdrop_url']
                if "t/p/" in backdrop:
                    backdrop = re.sub(r'/t/p/w\d+/', '/t/p/original/', backdrop)
                    backdrop = re.sub(r'/t/p/w\d+x\d+/', '/t/p/original/', backdrop)
                return backdrop
        except Exception as e:
            logger.error(f"TMDB backdrop error: {e}")
    
    ai_backdrop = await fetch_cinemeta_ai_poster(movie_name, is_series)
    if ai_backdrop:
        return ai_backdrop
        
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

def extract_languages_from_text(text: str) -> set:
    """Regex word boundaries ਨਾਲ ਭਾਸ਼ਾਵਾਂ ਲੱਭੋ — ਗਲਤ ਸਬ-ਸਟ੍ਰਿੰਗ ਨਾਲ ਗੜਬੜੀ ਨਹੀਂ ਹੋਵੇਗੀ"""
    found = set()
    text_lower = text.lower()
    # ਪਹਿਲਾਂ CAPTION_LANGUAGES ਦੀਆਂ ਕੁੰਜੀਆਂ ਨਾਲ word boundary match
    for lang_key, lang_name in CAPTION_LANGUAGES.items():
        if re.search(rf'\b{re.escape(lang_key)}\b', text_lower):
            found.add(lang_name)
    return found

def extract_media_info(filename: str, caption: str):
    filename_cleaned = clean_mentions_links(filename)
    filename_normalized = normalize(filename_cleaned)
    caption_clean = clean_mentions_links(caption).lower() if caption else ""

    tag = "#MOVIE"
    year = None
    
    quality = QUALITY_PATTERN.findall(filename_normalized)
    quality_str = ", ".join(quality) if quality else "N/A"
    ott_platform = extract_ott_platform(f"{filename_normalized} {caption_clean}")

    # ✅ Regex word boundaries ਨਾਲ ਭਾਸ਼ਾ ਡਿਟੈਕਟ ਕਰੋ
    lang_set = set()
    lang_set.update(extract_languages_from_text(filename_normalized))
    lang_set.update(extract_languages_from_text(caption_clean))
    language = ", ".join(sorted(lang_set)) if lang_set else "N/A"

    if EPISODE_CLEAN_PATTERN.search(filename_normalized):
        tag = "#SERIES"
    
    clean_name = EPISODE_CLEAN_PATTERN.sub(" ", filename_normalized)
    clean_name = QUALITY_PATTERN.sub(" ", clean_name)

    year_match = YEAR_PATTERN.search(clean_name)
    if year_match:
        year = year_match.group(1)
        idx = clean_name.find(year)
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
        details = {}
        tmdb_language_override = None
        
        if TMDB_POSTER:
            try:
                details = await get_movie_detailsx(base_name)
                if not details or details.get("error"):
                    error_tmdb = True
                else:
                    # TMDB ਤੋਂ original_language ਲਓ
                    orig_lang = details.get("original_language") or details.get("lang")
                    if orig_lang:
                        tmdb_language_override = TMDB_LANG_MAP.get(orig_lang.lower())
            except Exception:
                error_tmdb = True
                
        if not TMDB_POSTER or error_tmdb or not details:
            details = await get_movie_details(base_name) or {}

        rating_val = "N/A"
        if details.get("rating"):
            try:
                rating_val = f"{float(details.get('rating')):.1f}"
            except ValueError:
                pass

        year_val = media_info["year"]
        if not year_val and details.get("year"):
            year_val = str(details.get("year")).strip()
        
        is_series = (media_info["tag"] == "#SERIES")
        if not year_val and is_series:
            try:
                session = await get_session()
                encoded_query = urllib.parse.quote(base_name)
                search_url = f"https://v3-cinemeta.strem.io/catalog/series/top/search={encoded_query}.json"
                async with session.get(search_url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        metas = data.get("metas", [])
                        if metas and metas[0].get("year"):
                            raw_year = metas[0].get("year")
                            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', str(raw_year))
                            if year_match:
                                year_val = year_match.group(1)
            except Exception as e:
                logger.error(f"Error fetching series year from Cinemeta: {e}")

        year_val = year_val or None
        
        # ✅ Language: TMDB original_language ਨੂੰ ਪ੍ਰਾਥਮਿਕਤਾ ਦਿਓ, ਫਿਰ file/caption ਤੋਂ
        final_language = media_info["language"]
        if tmdb_language_override and tmdb_language_override != "N/A":
            # ਜੇ TMDB ਭਾਸ਼ਾ ਮਿਲੀ ਹੈ, ਤਾਂ ਉਸ ਨੂੰ ਪਹਿਲ ਦਿਓ
            if final_language == "N/A" or final_language == "Hindi" or len(final_language.split(",")) <= 1:
                final_language = tmdb_language_override
            else:
                # ਜੇ ਪਹਿਲਾਂ ਤੋਂ ਹੀ ਕਈ ਭਾਸ਼ਾਵਾਂ ਹਨ, ਤਾਂ TMDB ਵਾਲੀ ਨੂੰ ਜੋੜ ਦਿਓ (ਜੇ ਡੁਪਲੀਕੇਟ ਨਾ ਹੋਵੇ)
                existing = set(l.strip() for l in final_language.split(","))
                existing.add(tmdb_language_override)
                final_language = ", ".join(sorted(existing))
        elif final_language == "N/A":
            # ਕੋਈ ਭਾਸ਼ਾ ਨਾ ਮਿਲੀ, ਤਾਂ ਡਿਫਾਲਟ Hindi ਲਗਾਓ
            final_language = "Hindi"
        
        # Update file_data with final language
        file_data["language"] = final_language
        
        final_poster = await get_landscape_poster_only(base_name, is_series)

        if not final_poster:
            logger.info(f"❌ Poster NOT found for '{base_name}'. Skipping post creation to avoid text-only updates.")
            return

        existing_movie = await db.movie_updates.find_one({"_id": base_name})
        if existing_movie:
            file_exists = any(f.get("filename") == filename for f in existing_movie.get("files", []))
            
            update_fields = {}
            if existing_movie.get("rating") == "N/A" and rating_val != "N/A":
                update_fields["rating"] = rating_val
            if not existing_movie.get("year") and year_val:
                update_fields["year"] = year_val
            if not existing_movie.get("poster_url") and final_poster:
                update_fields["poster_url"] = final_poster
            # ✅ Language update ਜੇਕਰ ਪੁਰਾਣੀ language N/A ਹੈ ਜਾਂ ਗਲਤ ਹੈ
            if existing_movie.get("language") != final_language and final_language != "N/A":
                update_fields["language"] = final_language

            if not file_exists:
                await db.movie_updates.update_one(
                    {"_id": base_name}, 
                    {"$push": {"files": file_data}, "$set": update_fields} if update_fields else {"$push": {"files": file_data}}
                )
                await send_movie_update(bot, base_name, is_update=True)
            elif update_fields:
                await db.movie_updates.update_one({"_id": base_name}, {"$set": update_fields})
                await send_movie_update(bot, base_name, is_update=True)
            return

        movie_doc = {
            "_id": base_name,
            "files": [file_data],
            "poster_url": final_poster,   # ਇਹ backdrop URL ਹੈ (ਲੈਂਡਸਕੇਪ)
            "rating": rating_val,
            "year": year_val,
            "tag": media_info["tag"],
            "language": final_language,
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
        poster_url = movie_doc.get("poster_url")  # ਇਹ backdrop URL ਹੋਣਾ ਚਾਹੀਦਾ ਹੈ (landscape)

        if not poster_url:
            logger.info(f"⚠️ Blocked sending post for '{base_name}' because poster_url is missing.")
            return None

        sent_msg = None

        # ========== NEW: Generate title-only poster for new posts ==========
        if not is_update:
            # ਪਹਿਲੀ ਵਾਰ ਪੋਸਟ ਕਰ ਰਹੇ ਹਾਂ: backdrop 'ਤੇ ਟਾਈਟਲ ਲਿਖ ਕੇ ਭੇਜੋ
            image_bytes = await create_title_only_poster(poster_url, base_name)
            if image_bytes:
                try:
                    sent_msg = await bot.send_photo(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        photo=image_bytes,  # bytes
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    return await send_movie_update(bot, base_name, is_update)
                except Exception as img_err:
                    logger.error(f"Failed to send generated poster: {img_err}")
                    # fallback: send original poster URL
                    try:
                        sent_msg = await bot.send_photo(
                            chat_id=MOVIE_UPDATE_CHANNEL,
                            photo=poster_url,
                            caption=text,
                            reply_markup=buttons,
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as e:
                        logger.error(f"Fallback send_photo also failed: {e}")
                        return None
            else:
                # ਜੇਕਰ generate fail ਹੋਵੇ, ਤਾਂ ਅਸਲੀ URL ਭੇਜੋ
                try:
                    sent_msg = await bot.send_photo(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        photo=poster_url,
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    return await send_movie_update(bot, base_name, is_update)
                except Exception as e:
                    logger.error(f"Fallback send_photo failed: {e}")
                    return None
        else:
            # UPDATE: ਸਿਰਫ਼ caption edit ਕਰੋ (ਪੋਸਟਰ ਨੂੰ ਨਾ ਛੇੜੋ)
            if movie_doc.get("message_id"):
                try:
                    sent_msg = await bot.edit_message_caption(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_id=movie_doc["message_id"],
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except MessageNotModified:
                    sent_msg = movie_doc
                except MessageIdInvalid:
                    pass
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    return await send_movie_update(bot, base_name, is_update)
            # ਜੇ message_id ਨਾ ਹੋਵੇ (ਕੁਝ ਗੜਬੜ), ਤਾਂ new send ਕਰੋ
            if not sent_msg:
                # fallback to send as new (with title poster)
                image_bytes = await create_title_only_poster(poster_url, base_name)
                if image_bytes:
                    try:
                        sent_msg = await bot.send_photo(
                            chat_id=MOVIE_UPDATE_CHANNEL,
                            photo=image_bytes,
                            caption=text,
                            reply_markup=buttons,
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as e:
                        logger.error(f"Update fallback send failed: {e}")
                        return None
                else:
                    try:
                        sent_msg = await bot.send_photo(
                            chat_id=MOVIE_UPDATE_CHANNEL,
                            photo=poster_url,
                            caption=text,
                            reply_markup=buttons,
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as e:
                        logger.error(f"Update fallback send_photo failed: {e}")
                        return None

        if sent_msg and hasattr(sent_msg, 'id'):
            # Save message_id for future updates (if new send)
            if not is_update and movie_doc.get("message_id") is None:
                await db.movie_updates.update_one({"_id": base_name}, {"$set": {"message_id": sent_msg.id}})
            asyncio.create_task(verify_and_correct_post_with_ai(bot, sent_msg.id, base_name, buttons))
            return sent_msg

    except Exception as e:
        logger.error(f"Failed to push update layout: {e}")
    return None

# ============ AI DOUBLE CHECK & AUTO CORRECTION ENGINE ============

async def verify_and_correct_post_with_ai(bot, message_id: int, base_name: str, buttons):
    try:
        # ✅ 1 ਮਿੰਟ (60 ਸਕਿੰਟ) ਬਾਅਦ ਚੈੱਕ ਕਰੋ
        await asyncio.sleep(60)
        
        movie_doc = await db.movie_updates.find_one({"_id": base_name})
        if not movie_doc or not movie_doc.get("poster_url"):
            return

        correct_text = generate_movie_message(movie_doc, base_name)
        
        try:
            live_msg = await bot.get_messages(chat_id=MOVIE_UPDATE_CHANNEL, message_ids=message_id)
            if isinstance(live_msg, list) and live_msg:
                live_msg = live_msg[0]
                
            live_text = live_msg.caption if live_msg else ""
            
            if live_text and live_text.strip() == correct_text.strip():
                return
                
            logger.info(f"🔎 AI detected a mismatch in post ID {message_id}. Correcting automatically...")
            await bot.edit_message_caption(
                chat_id=MOVIE_UPDATE_CHANNEL,
                message_id=message_id,
                caption=correct_text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML
                )
            logger.info(f"✅ AI successfully auto-corrected post ID {message_id}!")
        except MessageNotModified:
            pass 
        except FloodWait as e:
            logger.warning(f"AI engine hit floodwait. Sleeping for {e.value} seconds.")
            await asyncio.sleep(e.value + 5)
            await verify_and_correct_post_with_ai(bot, message_id, base_name, buttons)
        except Exception as msg_err:
            logger.error(f"Error while fetching or editing live message for AI verification: {msg_err}")
            
    except Exception as e:
        logger.error(f"Critical error in AI Double-Check Engine: {e}")

# ============ GENERATE MOVIE MESSAGE ============

def generate_movie_message(movie_doc, base_name) -> str:
    all_languages = set()
    for file in movie_doc["files"]:
        if file.get("language") and file["language"] != "N/A":
            all_languages.update(l.strip() for l in file["language"].split(",") if l.strip())
    
    # ✅ ਜੇਕਰ movie_doc ਵਿੱਚ language ਸਟੋਰ ਹੈ, ਤਾਂ ਉਸ ਨੂੰ ਵੀ ਲਵਾਂ
    if movie_doc.get("language") and movie_doc["language"] != "N/A":
        all_languages.update(l.strip() for l in movie_doc["language"].split(",") if l.strip())
    
    language_str = " ".join(f"#{lang}" for lang in sorted(all_languages)) if all_languages else "#Hindi"
    
    title = html.escape(base_name.upper())
    title = re.sub(r'\b10BIT\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title).strip()
    
    year_val = str(movie_doc.get("year", "")).strip()
    year_val = re.sub(r'[()\[\]]', '', year_val)
    
    # [FIX] ਚੈੱਕ ਕਰੋ ਕਿ ਪੋਸਟ ਸੀਰੀਜ਼ (#SERIES) ਦੀ ਹੈ ਜਾਂ ਨਹੀਂ। ਜੇ ਸੀਰੀਜ਼ ਹੈ ਤਾਂ ਸਾਲ (Year) ਨਾ ਲਗਾਓ।
    is_series = (movie_doc.get("tag") == "#SERIES")
    
    if is_series:
        year_str = ""  # ਵੈੱਬ ਸੀਰੀਜ਼/ਐਪੀਸੋਡਸ ਲਈ ਸਾਲ ਬਿਲਕੁਲ ਗਾਇਬ
    else:
        year_str = f" ({html.escape(year_val)})" if year_val and year_val != "None" and year_val not in title else ""
    
    rating_raw = movie_doc.get("rating", "N/A")
    rating_str = f"{rating_raw}/10" if rating_raw != "N/A" else "N/A"
    
    return (
        f"🎬 <code>{title}{year_str}</code>\n"
        f"<i>📌 (Touch To Copy)</i>\n\n"
        f"⭐ IMDb: {rating_str}\n\n"
        f"➡ Audio Track:- 🔊 {language_str}\n\n"
        f"Added ✅"
)
