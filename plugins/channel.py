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
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import MessageIdInvalid, MessageNotModified, FloodWait
from pymongo.errors import DuplicateKeyError

from plugins.Dreamxfutures.Imdbposter import get_movie_detailsx, get_movie_details
from database.users_chats_db import db
from database.ia_filterdb import save_file
from info import (
    CHANNELS, MOVIE_UPDATE_CHANNEL,
    BAD_WORDS, LANDSCAPE_POSTER, TMDB_POSTER,
    TMDB_API_KEY, LOG_CHANNEL
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

# ============ CONSTANTS (unchanged) ============
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
MEDIA_FILTER = filters.document | filters.video | filters.audio

# ============ STRING HELPERS ============
def ensure_str(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return str(value)
    return str(value)

def is_valid_url(url):
    if not url or not isinstance(url, str):
        return False
    return url.startswith(('http://', 'https://'))

def safe_re_sub(pattern, repl, string, flags=0):
    string = ensure_str(string)
    if string is None:
        return None
    return re.sub(pattern, repl, string, flags)

# ============ GENERATE LANDSCAPE POSTER (ALWAYS RETURNS BYTES) ============
async def generate_landscape_poster(
    title: str,
    backdrop_url: Optional[str] = None,
    portrait_url: Optional[str] = None,
    cast_names: Optional[list] = None,
    tagline: Optional[str] = None,
    year: Optional[str] = None
) -> bytes:
    """
    ਹਮੇਸ਼ਾ ਇੱਕ landscape (16:9) image ਬਣਾਓ, title ਓਵਰਲੇਅ ਕਰਕੇ।
    ਜੇ backdrop ਮੌਜੂਦ, ਉਸ ਨੂੰ background ਵਜੋਂ ਵਰਤੋ; ਨਹੀਂ ਤਾਂ portrait (poster) ਨੂੰ center 'ਤੇ ਰੱਖੋ;
    ਨਹੀਂ ਤਾਂ dark gradient background।
    """
    # Default canvas size (16:9)
    W, H = 1920, 1080

    # Background image
    bg = None

    # 1. Try backdrop
    if backdrop_url and is_valid_url(backdrop_url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(backdrop_url, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        bg = Image.open(io.BytesIO(data)).convert("RGB")
                        bg = bg.resize((W, H), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"Failed to fetch backdrop: {e}")

    # 2. If backdrop failed, try portrait (poster)
    if bg is None and portrait_url and is_valid_url(portrait_url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(portrait_url, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        poster = Image.open(io.BytesIO(data)).convert("RGBA")
                        # Resize poster to fit within 70% of canvas height, keep aspect ratio
                        poster_w, poster_h = poster.size
                        target_h = int(H * 0.75)
                        target_w = int(poster_w * (target_h / poster_h))
                        if target_w > W:
                            target_w = W
                            target_h = int(poster_h * (target_w / poster_w))
                        poster = poster.resize((target_w, target_h), Image.Resampling.LANCZOS)
                        # Create canvas with dark gradient
                        canvas = Image.new("RGB", (W, H), (20, 20, 30))
                        # Paste poster centered
                        x = (W - target_w) // 2
                        y = (H - target_h) // 2 - 30
                        canvas.paste(poster, (x, y), poster)
                        bg = canvas
        except Exception as e:
            logger.warning(f"Failed to fetch portrait: {e}")

    # 3. If still no bg, use solid dark gradient (create manually)
    if bg is None:
        bg = Image.new("RGB", (W, H), (15, 15, 25))
        # Draw a simple gradient
        draw = ImageDraw.Draw(bg)
        for i in range(H):
            grad = int(20 + 50 * (i / H))
            draw.rectangle([(0, i), (W, i+1)], fill=(grad, grad, grad+20))

    # Convert to RGBA for overlays
    bg = bg.convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # ---------- Load fonts ----------
    font_paths = [
        "assets/font.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    title_font = sub_font = small_font = None
    for path in font_paths:
        try:
            title_font = ImageFont.truetype(path, int(W * 0.08))      # 8% of width
            sub_font = ImageFont.truetype(path, int(W * 0.035))
            small_font = ImageFont.truetype(path, int(W * 0.025))
            break
        except:
            continue
    if title_font is None:
        title_font = sub_font = small_font = ImageFont.load_default()

    # ---------- Gradient overlay (darken top & bottom) ----------
    for i in range(0, int(H * 0.35)):
        alpha = int(200 * (1 - i / (H * 0.35)))
        draw.rectangle([(0, i), (W, i+1)], fill=(0, 0, 0, alpha))
        y_bottom = H - i
        draw.rectangle([(0, y_bottom), (W, y_bottom+1)], fill=(0, 0, 0, alpha))

    # ---------- Cast (top) ----------
    cast_text = " | ".join((cast_names or [])[:3]).upper()
    if cast_text:
        bbox = draw.textbbox((0, 0), cast_text, font=sub_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw)//2, int(H * 0.08)), cast_text, font=sub_font, fill=(255, 215, 0, 255))

    # ---------- Title (center) ----------
    wrapped_title = textwrap.fill(title.upper(), width=14)
    bbox = draw.textbbox((0, 0), wrapped_title, font=title_font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text(((W - tw)//2, (H - th)//2 - th//2), wrapped_title, font=title_font, fill=(255, 255, 255, 255))

    # ---------- Tagline (below title) ----------
    if tagline:
        tagline = tagline.upper()
        bbox = draw.textbbox((0, 0), tagline, font=sub_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw)//2, (H//2) + int(H * 0.06)), tagline, font=sub_font, fill=(255, 255, 200, 255))

    # ---------- Year (bottom) ----------
    bottom_text = f"ONLY IN THEATRES  {year}" if year else "ONLY IN THEATRES"
    bbox = draw.textbbox((0, 0), bottom_text, font=small_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw)//2, H - int(H * 0.1)), bottom_text, font=small_font, fill=(255, 255, 255, 255))

    # ---------- Output ----------
    out = io.BytesIO()
    bg.convert("RGB").save(out, format="JPEG", quality=92)
    return out.getvalue()

# ============ EXTRACTION FUNCTIONS (unchanged) ============
def clean_mentions_links(text: str) -> str:
    return safe_re_sub(CLEAN_PATTERN, "", text or "").strip()

def normalize(s: str) -> str:
    s = safe_re_sub(NORMALIZE_PATTERN, " ", s)
    return re.sub(r"\s+", " ", s).strip()

def remove_ignored_words(text: str) -> str:
    words = text.split()
    cleaned = []
    for w in words:
        if w.lower() in IGNORE_WORDS:
            break
        cleaned.append(w)
    return " ".join(cleaned)

def extract_languages_from_text(text: str) -> set:
    found = set()
    text_lower = text.lower()
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

    lang_set = set()
    lang_set.update(extract_languages_from_text(filename_normalized))
    lang_set.update(extract_languages_from_text(caption_clean))
    language = ", ".join(sorted(lang_set)) if lang_set else "N/A"

    if EPISODE_CLEAN_PATTERN.search(filename_normalized):
        tag = "#SERIES"
    
    clean_name = safe_re_sub(EPISODE_CLEAN_PATTERN, " ", filename_normalized)
    clean_name = safe_re_sub(QUALITY_PATTERN, " ", clean_name)

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

    # Remove year to group same movies
    base_name = safe_re_sub(r'\b(19\d{2}|20\d{2})\b', '', base_name).strip()
    base_name = normalize(base_name)

    if tag == "#SERIES":
        base_name = safe_re_sub(r'\bS\d{1,2}\b', '', base_name, flags=re.IGNORECASE).strip()
        base_name = normalize(base_name)

    return {
        "base_name": base_name.title(),
        "tag": tag,
        "year": year,
        "quality": quality_str,
        "language": language,
        "ott_platform": ott_platform
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
    media.caption = message.caption or ""
    success, _ = await save_file(media)
    if not success:
        return
    try:
        if await db.movie_update_status(bot.me.id):
            await process_and_send_update(bot, media.file_name, media.caption)
    except Exception:
        logger.exception("Media processing exception.")

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
        logger.exception(f"Lock pipeline failure: {e}")

# ============ PROCESS WITH LOCK ============
async def _process_with_lock(bot, filename, caption, media_info, base_name):
    if not hasattr(db, 'movie_updates'):
        db.movie_updates = db.db.movie_updates

    file_data = {
        "filename": filename,
        "quality": media_info["quality"],
        "language": media_info["language"],
        "timestamp": datetime.now()
    }

    try:
        details = {}
        tmdb_language_override = None
        backdrop_url = None
        poster_path = None   # portrait

        if TMDB_POSTER:
            try:
                tmdb_data = await get_movie_detailsx(base_name)
                if tmdb_data and not tmdb_data.get("error"):
                    details = tmdb_data.copy()
                    backdrop_url = tmdb_data.get("backdrop_url")
                    poster_path = tmdb_data.get("poster_path")
                    orig_lang = tmdb_data.get("original_language")
                    if orig_lang:
                        tmdb_language_override = TMDB_LANG_MAP.get(orig_lang.lower())
            except Exception:
                pass
                
        if not details:
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
        year_val = year_val or None
        
        final_language = media_info["language"]
        if tmdb_language_override and tmdb_language_override != "N/A":
            if final_language == "N/A" or len(final_language.split(",")) <= 1:
                final_language = tmdb_language_override
            else:
                existing = set(l.strip() for l in final_language.split(","))
                existing.add(tmdb_language_override)
                final_language = ", ".join(sorted(existing))
        elif final_language == "N/A":
            final_language = "Hindi"
        
        file_data["language"] = final_language

        # Ensure poster_path URL
        portrait_url = None
        if poster_path:
            if not poster_path.startswith(('http://', 'https://')):
                poster_path = f"https://image.tmdb.org/t/p/original{poster_path}"
            portrait_url = poster_path

        # We will always generate landscape poster using available images
        # No need to store poster_url in DB, we'll regenerate on each update
        # but we keep for reference

        # Build movie_data for poster generation
        movie_data = {
            "title": ensure_str(details.get("title") or base_name),
            "tagline": ensure_str(details.get("tagline", "")),
            "cast_names": [ensure_str(c) for c in details.get("cast", [])],
            "year": year_val or details.get("release_date", "").split("-")[0] if details.get("release_date") else "",
            "backdrop_url": ensure_str(backdrop_url),
            "portrait_url": portrait_url
        }

        existing_movie = await db.movie_updates.find_one({"_id": base_name})
        if existing_movie:
            file_exists = any(f.get("filename") == filename for f in existing_movie.get("files", []))
            update_fields = {}
            if existing_movie.get("rating") == "N/A" and rating_val != "N/A":
                update_fields["rating"] = rating_val
            if not existing_movie.get("year") and year_val:
                update_fields["year"] = year_val
            if existing_movie.get("language") != final_language and final_language != "N/A":
                update_fields["language"] = final_language
            # Update movie_data for future regeneration
            update_fields["movie_data"] = movie_data

            if not file_exists:
                await db.movie_updates.update_one(
                    {"_id": base_name}, 
                    {"$push": {"files": file_data}, "$set": update_fields}
                )
                await send_movie_update(bot, base_name, is_update=True, movie_data=movie_data)
            elif update_fields:
                await db.movie_updates.update_one({"_id": base_name}, {"$set": update_fields})
                await send_movie_update(bot, base_name, is_update=True, movie_data=movie_data)
            return

        movie_doc = {
            "_id": base_name,
            "files": [file_data],
            "rating": rating_val,
            "year": year_val,
            "tag": media_info["tag"],
            "language": final_language,
            "movie_data": movie_data,
            "message_id": None,
            "is_posted": True
        }
        
        try:
            await db.movie_updates.insert_one(movie_doc)
            msg = await send_movie_update(bot, base_name, is_update=False, movie_data=movie_data)
            if msg:
                await db.movie_updates.update_one({"_id": base_name}, {"$set": {"message_id": msg.id}})
        except DuplicateKeyError:
            await db.movie_updates.update_one({"_id": base_name}, {"$push": {"files": file_data}})
            await send_movie_update(bot, base_name, is_update=True, movie_data=movie_data)

    except Exception as e:
        logger.error(f"Process error: {e}")

# ============ SEND MOVIE UPDATE (ALWAYS WITH GENERATED POSTER) ============
async def send_movie_update(bot, base_name, is_update=False, movie_data=None):
    try:
        movie_doc = await db.movie_updates.find_one({"_id": base_name})
        if not movie_doc:
            return None

        if not movie_data:
            movie_data = movie_doc.get("movie_data", {})
            if not movie_data:
                movie_data = {}
            if not movie_data.get("title"):
                movie_data["title"] = base_name
            # ensure strings
            movie_data = {k: ensure_str(v) if isinstance(v, (str, bytes)) else v for k, v in movie_data.items()}
            if isinstance(movie_data.get("cast_names"), list):
                movie_data["cast_names"] = [ensure_str(c) for c in movie_data["cast_names"]]

        text = generate_movie_message(movie_doc, base_name)
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton('🔥 𝐉𝐎𝐈𝐍 𝐑𝐄𝐐𝐔𝐄𝐒𝐓 𝐆𝐑𝐎𝐔𝐏 ⚡', url="https://t.me/+l-EIo3NnnJAxODE9")]])

        # Generate landscape poster bytes (always succeeds)
        poster_bytes = await generate_landscape_poster(
            title=movie_data.get("title", base_name),
            backdrop_url=movie_data.get("backdrop_url"),
            portrait_url=movie_data.get("portrait_url"),
            cast_names=movie_data.get("cast_names"),
            tagline=movie_data.get("tagline"),
            year=movie_data.get("year")
        )

        if not poster_bytes:
            logger.error(f"Failed to generate poster for {base_name}")
            return None

        sent_msg = None

        # ---- UPDATE CASE ----
        if is_update and movie_doc.get("message_id"):
            media = InputMediaPhoto(media=poster_bytes, caption=text, parse_mode=enums.ParseMode.HTML)
            try:
                sent_msg = await bot.edit_message_media(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    message_id=movie_doc["message_id"],
                    media=media,
                    reply_markup=buttons
                )
            except MessageNotModified:
                sent_msg = movie_doc
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await send_movie_update(bot, base_name, is_update, movie_data)
            except MessageIdInvalid:
                is_update = False
            except Exception as e:
                logger.error(f"Edit media error: {e}")
                try:
                    sent_msg = await bot.edit_message_caption(
                        chat_id=MOVIE_UPDATE_CHANNEL,
                        message_id=movie_doc["message_id"],
                        caption=text,
                        reply_markup=buttons,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass

            if sent_msg:
                return sent_msg
            else:
                # If editing fails, try sending new (but avoid duplicate)
                # We'll treat as new post
                is_update = False

        # ---- NEW POST CASE (or fallback) ----
        if not is_update:
            try:
                sent_msg = await bot.send_photo(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    photo=poster_bytes,
                    caption=text,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await send_movie_update(bot, base_name, is_update, movie_data)
            except Exception as e:
                logger.error(f"Send photo error: {e}")
                return None

        if sent_msg and hasattr(sent_msg, 'id'):
            # Only update message_id if it's a new post or if previous didn't have one
            if not is_update or not movie_doc.get("message_id"):
                await db.movie_updates.update_one({"_id": base_name}, {"$set": {"message_id": sent_msg.id}})
            asyncio.create_task(verify_and_correct_post_with_ai(bot, sent_msg.id, base_name, buttons, movie_data))
            return sent_msg

    except Exception as e:
        logger.error(f"Send update error: {e}")
    return None

# ============ AI VERIFICATION ============
async def verify_and_correct_post_with_ai(bot, message_id: int, base_name: str, buttons, movie_data=None):
    try:
        await asyncio.sleep(60)
        movie_doc = await db.movie_updates.find_one({"_id": base_name})
        if not movie_doc:
            return

        correct_text = generate_movie_message(movie_doc, base_name)
        try:
            live_msg = await bot.get_messages(chat_id=MOVIE_UPDATE_CHANNEL, message_ids=message_id)
            if isinstance(live_msg, list):
                live_msg = live_msg[0]
            live_text = live_msg.caption if live_msg else ""
            if live_text and live_text.strip() == correct_text.strip():
                return
            logger.info(f"🔎 AI fixing post {message_id}")
            await bot.edit_message_caption(
                chat_id=MOVIE_UPDATE_CHANNEL,
                message_id=message_id,
                caption=correct_text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML
            )
        except MessageNotModified:
            pass
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
            await verify_and_correct_post_with_ai(bot, message_id, base_name, buttons, movie_data)
        except Exception as e:
            logger.error(f"AI error: {e}")
    except Exception as e:
        logger.error(f"AI critical: {e}")

# ============ CAPTION GENERATOR ============
def generate_movie_message(movie_doc, base_name) -> str:
    all_languages = set()
    for file in movie_doc["files"]:
        if file.get("language") and file["language"] != "N/A":
            all_languages.update(l.strip() for l in file["language"].split(","))
    if movie_doc.get("language") and movie_doc["language"] != "N/A":
        all_languages.update(l.strip() for l in movie_doc["language"].split(","))
    
    language_str = " ".join(f"#{lang}" for lang in sorted(all_languages)) if all_languages else "#Hindi"
    title = html.escape(ensure_str(base_name.upper()))
    title = re.sub(r'\b10BIT\b', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title).strip()
    
    year_val = ensure_str(movie_doc.get("year", "")).strip()
    year_val = re.sub(r'[()\[\]]', '', year_val)
    is_series = (movie_doc.get("tag") == "#SERIES")
    year_str = "" if is_series else f" ({year_val})" if year_val and year_val not in title else ""
    
    rating_raw = ensure_str(movie_doc.get("rating", "N/A"))
    rating_str = f"{rating_raw}/10" if rating_raw != "N/A" else "N/A"
    
    return (
        f"🎬 <code>{title}{year_str}</code>\n"
        f"<i>📌 (Touch To Copy)</i>\n\n"
        f"⭐ IMDb: {rating_str}\n\n"
        f"➡ Audio Track:- 🔊 {language_str}\n\n"
        f"Added ✅"
)
