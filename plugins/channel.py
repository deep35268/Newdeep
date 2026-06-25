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
    "rarbg", "dub", "sub", "sample", "mkv", "aac", "combined",
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
    "apple", "hoichoi", "sunnxt", "viki"
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
NORMALIZE_PATTERN = re.compile(r"[._]+|[()\[\]{}:;'–!,.?_]")
QUALITY_PATTERN = re.compile(
    r"\b(?:HDCam|HDTC|CamRip|TS|TC|TeleSync|DVDScr|DVDRip|PreDVD|"
    r"WEBRip|WEB-DL|TVRip|HDTV|WEB DL|WebDl|BluRay|BRRip|BDRip|"
    r"360p|480p|720p|1080p|2160p|4K|1440p|540p|240p|140p|HEVC|HDRip)\b", 
    re.IGNORECASE
)
YEAR_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:19|20)\d{2}(?![A-Za-z0-9])")
RANGE_REGEX = re.compile(r'\bS(\d{1,2})[^\w\n\r]*E(?:p(?:isode)?)?0*(\d{1,2})\s*(?:to|-)\s*(?:E(?:p(?:isode)?)?)?0*(\d{1,3})', re.IGNORECASE)
SINGLE_REGEX = re.compile(r'\bS(\d{1,2})[^\w\n\r]*E(?:p(?:isode)?)?0*(\d{1,3})', re.IGNORECASE)
NAMED_REGEX = re.compile(r'Season\s*0*(\d{1,2})[\s\-,:]*Ep(?:isode)?\s*0*(\d{1,3})', re.IGNORECASE)
EP_ONLY_RANGE = re.compile(r'\b(?:EP|Episode)0*(\d{1,3})\s*-\s*0*(\d{1,3})\b', re.IGNORECASE)

MEDIA_FILTER = filters.document | filters.video | filters.audio
locks = defaultdict(asyncio.Lock)

# ============ LANDSCAPE POSTER GENERATOR ============

class LandscapePosterGenerator:
    """Landscape Poster Generator - Only Landscape, No Vertical Fallback"""
    
    @staticmethod
    async def generate_landscape(vertical_poster_url: str, movie_name: str = "") -> Optional[str]:
        """
        ਖੜ੍ਹੇ ਪੋਸਟਰ ਨੂੰ ਛੋਟਾ ਕਰਕੇ ਸਾਈਡਾਂ 'ਤੇ ਕਾਲੀ ਜਗ੍ਹਾ (Black Bars) ਪਾ ਕੇ 16:9 Landscape ਬਣਾਉਣਾ
        """
        try:
            if not vertical_poster_url:
                return None
            
            # Clean TMDB URL to original quality
            if "t/p/" in vertical_poster_url:
                vertical_poster_url = re.sub(r'/t/p/w\d+/', '/t/p/original/', vertical_poster_url)
                vertical_poster_url = re.sub(r'/t/p/w\d+x\d+/', '/t/p/original/', vertical_poster_url)
            
            encoded_url = urllib.parse.quote_plus(vertical_poster_url)
            
            # w=1280 & h=720 (16:9 Landscape)
            # fit=contain (ਪੋਸਟਰ ਛੋਟਾ ਹੋ ਕੇ ਸੈਂਟਰ ਚ ਰਹੇਗਾ)
            # cbg=000000 (ਸਾਈਡਾਂ ਤੇ ਕਾਲਾ ਰੰਗ ਆਏਗਾ, ਬਲਰ ਹਟਾ ਦਿੱਤਾ ਹੈ)
            landscape_url = (
                f"https://images.weserv.nl/"
                f"?url={encoded_url}"
                f"&w=1280&h=720"
                f"&fit=contain"
                f"&cbg=000000"
                f"&a=c"
                f"&q=100"
                f"&output=jpg"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.head(landscape_url, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"✅ Landscape (with Black Bars) generated: {movie_name}")
                        return landscape_url
                    else:
                        logger.warning(f"⚠️ Landscape generation failed for: {movie_name}")
                        return None
                    
        except Exception as e:
            logger.error(f"❌ Error generating landscape: {e}")
            return None

# ============ POSTER FETCHING FUNCTIONS ============

async def fetch_free_landscape_poster(query: str) -> Optional[str]:
    """Fetch free landscape poster from DuckDuckGo"""
    try:
        search_url = "https://html.duckduckgo.com/html/"
        payload = {'q': f"{query} movie backdrop wallpaper landscape"}
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
                                    if resp.status == 200:
                                        content_type = resp.headers.get('content-type', '')
                                        if 'image' in content_type:
                                            return actual_url
    except Exception as e:
        logger.error(f"Free Scraping Search Error: {e}")
    return None

async def get_landscape_poster_only(movie_name: str, vertical_poster: Optional[str] = None) -> Optional[str]:
    if LANDSCAPE_POSTER:
        try:
            details = await get_movie_detailsx(movie_name)
            if details and details.get('backdrop_url'):
                backdrop = details['backdrop_url']
                if "t/p/" in backdrop:
                    backdrop = re.sub(r'/t/p/w\d+/', '/t/p/original/', backdrop)
                    backdrop = re.sub(r'/t/p/w\d+x\d+/', '/t/p/original/', backdrop)
                logger.info(f"✅ TMDB Backdrop found: {movie_name}")
                return backdrop
        except Exception as e:
            logger.error(f"TMDB backdrop error: {e}")
    
    landscape = await fetch_free_landscape_poster(movie_name)
    if landscape:
        logger.info(f"✅ Web Landscape found: {movie_name}")
        return landscape
    
    if vertical_poster:
        generator = LandscapePosterGenerator()
        landscape = await generator.generate_landscape(vertical_poster, movie_name)
        if landscape:
            logger.info(f"✅ Generated Landscape from vertical: {movie_name}")
            return landscape
    
    logger.warning(f"❌ No landscape found for: {movie_name}")
    return None

# ============ CLEANING AND EXTRACTION FUNCTIONS ============

def clean_mentions_links(text: str) -> str:
    return CLEAN_PATTERN.sub("", text or "").strip()

def normalize(s: str) -> str:
    s = NORMALIZE_PATTERN.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()

def remove_ignored_words(text: str) -> str:
    IGNORE_WORDS_LOWER = {w.lower() for w in IGNORE_WORDS}
    return " ".join(word for word in text.split() if word.lower() not in IGNORE_WORDS_LOWER)

def get_qualities(text: str) -> str:
    qualities = QUALITY_PATTERN.findall(text)
    return ", ".join(qualities) if qualities else "N/A"

def extract_ott_platform(text: str) -> str:
    text = text.lower()
    platforms = {plat for key, plat in OTT_PLATFORMS.items() if key in text}
    return " | ".join(platforms) if platforms else "N/A"

def extract_season_episode(filename: str) -> Tuple[Optional[int], Optional[str]]:
    if m := EP_ONLY_RANGE.search(filename):
        return 1, f"{int(m.group(1))}-{int(m.group(2))}"
    for pattern in (RANGE_REGEX, SINGLE_REGEX, NAMED_REGEX):
        if m := pattern.search(filename):
            season = int(m.group(1))
            ep = f"{m.group(2)}-{m.group(3)}" if pattern == RANGE_REGEX else m.group(2)
            return season, ep
    return None, None

def extract_media_info(filename: str, caption: str):
    filename = normalize(clean_mentions_links(filename).title())
    caption_clean = clean_mentions_links(caption).lower() if caption else ""
    unified = f"{caption_clean} {filename.lower()}".strip()

    season = episode = year = None
    tag = "#MOVIE"
    processed_raw = base_raw = filename
    quality = get_qualities(caption_clean) or get_qualities(filename.lower()) or "N/A"
    ott_platform = extract_ott_platform(f"{filename} {caption_clean}")

    lang_keys = {k for k in CAPTION_LANGUAGES if k in caption_clean or k in filename.lower()}
    language = ", ".join(sorted({CAPTION_LANGUAGES[k] for k in lang_keys})) if lang_keys else "N/A"

    season, episode = extract_season_episode(filename)
    if season is not None:
        tag = "#SERIES"
        if m := (RANGE_REGEX.search(filename) or SINGLE_REGEX.search(filename) or NAMED_REGEX.search(filename) or EP_ONLY_RANGE.search(filename)):
            match_str = m.group(0)
            start_idx = filename.lower().find(match_str.lower())
            end_idx = start_idx + len(match_str)
            processed_raw = filename[:end_idx]
            base_raw = filename[:start_idx]
            if year_match := YEAR_PATTERN.search(filename.lower()[end_idx:]):
                y = year_match.group(0)
                yi = filename.lower().find(y, end_idx)
                if yi != -1:
                    processed_raw = filename[:yi+4]
                    base_raw += f" {y}"
    else:
        if year_match := YEAR_PATTERN.search(unified):
            year = year_match.group(0)
            year_idx = filename.lower().find(year.lower())
            if year_idx != -1:
                processed_raw = filename[:year_idx + 4]
                base_raw = processed_raw
        else:
            if qual_match := QUALITY_PATTERN.search(unified):
                qual_str = qual_match.group(0)
                qual_idx = filename.lower().find(qual_str.lower())
                if qual_idx != -1:
                    processed_raw = filename[:qual_idx]
                    base_raw = processed_raw

    base_name = normalize(remove_ignored_words(normalize(base_raw)))
    if year and year not in base_name:
        base_name += f" {year}"

    if base_name.endswith(")"):
        base_name = re.sub(r"\s+\(\d{4}\)$", "", base_name)
        if year:
            base_name += f" {year}"

    def _strip_season_episode_tokens(name: str) -> str:
        if not name:
            return name

        year_match = re.search(r'\(?\b(19|20)\d{2}\b\)?\s*$', name)
        year_part = ""
        if year_match:
            year_part = year_match.group(0)
            name = name[:year_match.start()].strip()

        patterns = [
            r'\bS\d{1,2}E\d{1,2}\b', r'\bS\d{1,2}\b', r'\bE\d{1,2}\b',
            r'\b\d{1,2}x\d{1,2}\b', r'\bSeason\s*\d{1,2}\b',
            r'\bEp(?:isode)?\.?\s*\d{1,3}\b', r'\bEpisode\s*\d{1,3}\b', r'\bPart\s*\d{1,2}\b'
        ]

        for p in patterns:
            name = re.sub(p, ' ', name, flags=re.IGNORECASE)

        name = re.sub(r'[_\.\-]+', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()

        if year_part:
            y = re.search(r'(19|20)\d{2}', year_part)
            if y:
                name = f"{name} {y.group(0)}"

        return name.strip()

    base_name = _strip_season_episode_tokens(base_name)
    if not base_name:
        base_name = normalize(remove_ignored_words(normalize(processed_raw))) or filename

    return {
        "processed": normalize(processed_raw),
        "base_name": base_name,
        "tag": tag,
        "season": season,
        "episode": episode,
        "year": year,
        "quality": quality,
        "ott_platform": ott_platform,
        "language": language
    }

# ============ MAIN HANDLERS ============

@Client.on_message(filters.chat(CHANNELS) & MEDIA_FILTER)
async def media_handler(bot, message):
    media = next(
        (getattr(message, ft) for ft in ("document", "video", "audio")
         if getattr(message, ft, None)),
        None
    )
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
        processed = media_info["processed"]

        movie_key = f"{base_name.lower()}_{media_info['year'] or ''}"
        
        if len(POSTED_MOVIES) > MAX_CACHE_SIZE:
            POSTED_MOVIES.clear()
        
        if movie_key in POSTED_MOVIES:
            return

        lock = locks[base_name]
        async with lock:
            if movie_key in POSTED_MOVIES:
                return
            POSTED_MOVIES.add(movie_key)
            await _process_with_lock(bot, filename, caption, media_info, base_name, processed)
            
            await asyncio.sleep(15)
            POSTED_MOVIES.discard(movie_key)

    except PyMongoError as e:
        logger.error(f"Database error in process_and_send_update: {e}")
    except Exception as e:
        logger.exception(f"Processing failed in process_and_send_update: {e}")

# ============ PROCESS WITH LOCK ============

async def _process_with_lock(bot, filename, caption, media_info, base_name, processed):
    if not hasattr(db, 'movie_updates'):
        db.movie_updates = db.db.movie_updates

    error_tmdb = False
    
    file_data = {
        "filename": filename,
        "processed": processed,
        "quality": media_info["quality"],
        "language": media_info["language"],
        "ott_platform": media_info["ott_platform"],
        "timestamp": datetime.now(),
        "tag": media_info["tag"],
        "season": media_info["season"],
        "episode": media_info["episode"]
    }

    try:
        existing_movie = await db.movie_updates.find_one({"_id": base_name})
        
        if existing_movie:
            file_exists = any(f.get("filename") == filename for f in existing_movie.get("files", []))
            
            if not file_exists:
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$push": {"files": file_data}}
                )
                
                if not existing_movie.get("is_posted", False):
                    details = {}
                    if TMDB_POSTER:
                        try:
                            details = await get_movie_detailsx(base_name)
                            if not details or details.get("error") or (not details.get("poster_url") and not details.get("backdrop_url")):
                                error_tmdb = True
                        except Exception:
                            error_tmdb = True
                    if not TMDB_POSTER or error_tmdb or not details:
                        details = await get_movie_details(base_name) or {}
                    
                    final_poster = await get_landscape_poster_only(base_name, details.get("poster_url"))
                    
                    if final_poster:
                        update_data = {
                            "poster_url": final_poster,
                            "is_posted": True
                        }
                        if details.get("rating"):
                            try:
                                r = float(details.get("rating"))
                                if 0.0 < r <= 10.0:
                                    update_data["rating"] = f"{r:.1f}"
                            except ValueError:
                                pass
                        if details.get("year"):
                            update_data["year"] = details.get("year")
                        
                        update_data["imdb_url"] = details.get("url") if error_tmdb else details.get("tmdb_url", "")
                        
                        await db.movie_updates.update_one(
                            {"_id": base_name},
                            {"$set": update_data}
                        )
                        msg = await send_movie_update(bot, base_name, is_update=False)
                        if msg:
                            await db.movie_updates.update_one(
                                {"_id": base_name},
                                {"$set": {"message_id": msg.id, "is_photo": True}}
                            )
                    else:
                        logger.info(f"📦 No poster for {base_name}, file appended but not posted yet.")
                else:
                    await send_movie_update(bot, base_name, is_update=True)
            return

        # NEW MOVIE
        details = {}
        if TMDB_POSTER:
            try:
                details = await get_movie_detailsx(base_name)
                if not details or details.get("error") or (not details.get("poster_url") and not details.get("backdrop_url")):
                    error_tmdb = True
            except Exception:
                error_tmdb = True
                
        if not TMDB_POSTER or error_tmdb or not details:
            details = await get_movie_details(base_name) or {}

        raw_genres = details.get("genres", "N/A")
        if isinstance(raw_genres, str):
            genre_list = [g.strip() for g in raw_genres.split(",")]
            genres = ", ".join(g for g in genre_list if g in STANDARD_GENRES) or "N/A"
        else:
            genres = ", ".join(g for g in raw_genres if g in STANDARD_GENRES) or "N/A"
        
        final_poster = await get_landscape_poster_only(base_name, details.get("poster_url"))
        
        rating_val = "N/A"
        try:
            raw_rating = details.get("rating")
            if raw_rating is not None:
                r = float(raw_rating)
                if 0.0 < r <= 10.0:
                    rating_val = f"{r:.1f}"
        except (TypeError, ValueError):
            pass

        year_val = details.get("year") or media_info["year"]
        imdb_url = details.get("url", "") if error_tmdb else details.get("tmdb_url", "")

        movie_doc = {
            "_id": base_name,
            "files": [file_data],
            "poster_url": final_poster,
            "genres": genres,
            "rating": rating_val,
            "imdb_url": imdb_url,
            "year": year_val,
            "tag": media_info["tag"],
            "ott_platform": media_info["ott_platform"],
            "message_id": None,
            "is_photo": False,
            "error_tmdb": error_tmdb,
            "is_backdrop": True,
            "is_landscape": final_poster is not None,
            "is_posted": final_poster is not None
        }
        
        await db.movie_updates.insert_one(movie_doc)
        
        if final_poster:
            msg = await send_movie_update(bot, base_name, is_update=False)
            if msg:
                await db.movie_updates.update_one(
                    {"_id": base_name},
                    {"$set": {"message_id": msg.id, "is_photo": True}}
                )
        else:
            logger.info(f"📦 New movie {base_name} saved without poster – not posted yet.")

    except DuplicateKeyError:
        await db.movie_updates.update_one(
            {"_id": base_name},
            {"$push": {"files": file_data}}
        )
        movie = await db.movie_updates.find_one({"_id": base_name})
        if movie and movie.get("is_posted", False):
            await send_movie_update(bot, base_name, is_update=True)
    except Exception as e:
        logger.error(f"Error in _process_with_lock: {e}")

# ============ SEND MOVIE UPDATE ============

async def send_movie_update(bot, base_name, is_update=False):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            movie_doc = await db.movie_updates.find_one({"_id": base_name})
            if not movie_doc:
                return None

            text = generate_movie_message(movie_doc, base_name)
            
            buttons = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    text='⚜️ Request Group ⚜️',
                    url="https://t.me/+l-EIo3NnnJAxODE9"
                )
            ]])
            
            if is_update and movie_doc.get("message_id"):
                try:
                    if movie_doc.get("is_photo"):
                        msg = await bot.edit_message_caption(
                            chat_id=MOVIE_UPDATE_CHANNEL,
                            message_id=movie_doc["message_id"],
                            caption=text,
                            reply_markup=buttons,
                            parse_mode=enums.ParseMode.HTML
                        )
                    else:
                        msg = await bot.edit_message_text(
                            chat_id=MOVIE_UPDATE_CHANNEL,
                            message_id=movie_doc["message_id"],
                            text=text,
                            reply_markup=buttons,
                            parse_mode=enums.ParseMode.HTML
                        )
                    return msg if msg else movie_doc
                except MessageNotModified:
                    return movie_doc
                except MessageIdInvalid:
                    pass

            poster_url = movie_doc.get("poster_url")
            
            if poster_url and not LINK_PREVIEW:
                msg = await bot.send_photo(
                    chat_id=MOVIE_UPDATE_CHANNEL,
                    photo=poster_url,
                    caption=text,
                    reply_markup=buttons,
                    parse_mode=enums.ParseMode.HTML
                )
                is_photo = True
            else:
                send_params = {
                    "chat_id": MOVIE_UPDATE_CHANNEL,
                    "text": text,
                    "reply_markup": buttons,
                    "parse_mode": enums.ParseMode.HTML,
                    "disable_web_page_preview": True
                }
                if poster_url and LINK_PREVIEW:
                    send_params["invert_media"] = ABOVE_PREVIEW
                msg = await bot.send_message(**send_params)
                is_photo = False

            await db.movie_updates.update_one(
                {"_id": base_name},
                {"$set": {"message_id": msg.id, "is_photo": is_photo}}
            )
            return msg
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
        except Exception as e:
            logger.error(f"Failed to send movie update: {e}")
            break
    return None

# ============ GENERATE MOVIE MESSAGE ============

def generate_movie_message(movie_doc, base_name) -> str:
    all_languages = set()
    for file in movie_doc["files"]:
        if file.get("language") and file["language"] != "N/A":
            all_languages.update(l.strip() for l in file["language"].split(",") if l.strip())
    
    language_str = " ".join(f"#{lang}" for lang in sorted(all_languages)) if all_languages else "#Hindi"
    
    title = base_name.upper()
    year_val = movie_doc.get("year")
    
    # ਚੈੱਕ ਕਰੋ ਜੇਕਰ ਟਾਈਟਲ ਦੇ ਅੰਦਰ ਪਹਿਲਾਂ ਤੋਂ ਹੀ ਉਹ ਸਾਲ ਮੌਜੂਦ ਹੈ ਤਾਂ ਦੁਬਾਰਾ (year) ਨਾ ਲਿਖੇ
    if year_val and str(year_val) in title:
        year_str = ""
    else:
        year_str = f" ({year_val})" if year_val else ""
    
    rating_raw = movie_doc.get("rating", "N/A")
    rating_str = f"{float(rating_raw):.1f}/10" if rating_raw != "N/A" else "N/A"
    
    message = (
        f"🎬 {title}{year_str}\n\n"
        f"⭐ IMDb: {rating_str}\n\n"
        f"➡ Audio Track:- 🔊 {language_str}\n\n"
        f"Added ✅"
    )
    return message
