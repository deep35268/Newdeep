import re
import os
import aiohttp
import asyncio
import random
import urllib.parse
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageIdInvalid, MessageNotModified

# info.py ਅਤੇ ਹੋਰ ਜ਼ਰੂਰੀ ਫਾਈਲਾਂ ਤੋਂ ਸੈਟਿੰਗਾਂ ਇੰਪੋਰਟ ਕਰਨਾ
from info import (
    CHANNELS, 
    MOVIE_UPDATE_CHANNEL, 
    GRP_LNK, 
    name,
    BAD_WORDS
)

# ਡਾਟਾਬੇਸ ਸੇਵਿੰਗ ਸਿਸਟਮ (ਜੇਕਰ ਤੁਹਾਡੇ ਬੋਟ ਵਿੱਚ ਹੈ)
try:
    from database.ia_filterdb import save_file
except ImportError:
    def save_file(*args, **kwargs): pass

logger = logging.getLogger(__name__)

# ਡੁਪਲੀਕੇਟ ਪੋਸਟਾਂ ਨੂੰ ਰੋਕਣ ਲਈ ਯੂਨੀਕ ਲਿਸਟ
POSTED_MOVIES = set()

# ਕੁਆਲਿਟੀ ਅਤੇ ਭਾਸ਼ਾ ਲੱਭਣ ਲਈ ਪੈਟਰਨ
QUALITY_KEYWORDS = ["2160p", "1080p", "720p", "480p", "360p", "4k", "uhd", "bluray", "web-dl", "webdl", "webrip", "hdrip", "brrip", "dvdrip", "hdtv"]
AUDIO_PATTERNS = {
    "hindi": "Hindi", 
    "english": "English", 
    "eng": "English", 
    "tamil": "Tamil", 
    "telugu": "Telugu", 
    "punjabi": "Punjabi", 
    "dual": "Dual Audio", 
    "multi": "Multi Audio"
}

def clean_movie_title(filename: str):
    """
    ਫਾਈਲ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਫਾਲਤੂ ਅੱਖਰ ਹਟਾ ਕੇ ਸਾਫ਼ ਨਾਮ, ਸਾਲ ਅਤੇ ਭਾਸ਼ਾ ਕੱਢਣਾ
    """
    try:
        name_str = str(filename)
        # ਐਕਸਟੈਂਸ਼ਨ ਹਟਾਉਣਾ
        name_str = re.sub(r"\.(mkv|mp4|avi|webm|mov)$", "", name_str, flags=re.IGNORECASE)
        # ਯੂਜ਼ਰਨੇਮ ਅਤੇ ਲਿੰਕ ਹਟਾਉਣੇ
        name_str = re.sub(r"@[\w_]+", " ", name_str)
        name_str = re.sub(r"https?://\S+", " ", name_str)
        name_str = re.sub(r"\[.*?\]|\(.*?\)", " ", name_str)
        name_str = name_str.replace(".", " ").replace("_", " ").replace("-", " ")
        
        # ਭਾਸ਼ਾ ਚੈੱਕ ਕਰਨਾ
        found_audios = []
        name_lower = name_str.lower()
        for key, val in AUDIO_PATTERNS.items():
            if re.search(rf"\b{key}\b", name_lower):
                if val not in found_audios: found_audios.append(val)
        if not found_audios: found_audios = ["Hindi"]
        
        # ORG ਟਰੈਕ ਚੈੱਕ ਕਰਨਾ
        is_org = bool(re.search(r"\b(org|original)\b", name_lower))
        
        # ਸਾਲ (Year) ਲੱਭਣਾ
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name_str)
        year = year_match.group(1) if year_match else ""
        
        # ਕੁਆਲਿਟੀ ਵਾਲੀ ਜਗ੍ਹਾ ਤੋਂ ਨਾਮ ਕੱਟਣਾ
        cutoff = len(name_str)
        if year_match: cutoff = min(cutoff, year_match.start())
        for kw in QUALITY_KEYWORDS:
            match = re.search(rf"\b{kw}\b", name_lower)
            if match: cutoff = min(cutoff, match.start())
                
        clean_title = name_str[:cutoff].strip()
        # ਜੇਕਰ ਬੁਰੇ ਸ਼ਬਦ (Bad Words) ਲਿਸਟ ਵਿੱਚ ਹੋਣ ਤਾਂ ਹਟਾਉਣੇ
        for word in BAD_WORDS:
            clean_title = re.sub(rf"\b{word}\b", "", clean_title, flags=re.IGNORECASE)
            
        if not clean_title: clean_title = name_str.strip()
        return re.sub(r"\s+", " ", clean_title).strip(), year, found_audios, is_org
    except Exception:
        return "Movie", "", ["Hindi"], False

async def fetch_tmdb_data(title: str, year: str):
    """
    TMDB ਤੋਂ ਲੈਂਡਸਕੇਪ ਪੋਸਟਰ (Backdrop) ਅਤੇ IMDb ਰੇਟਿੰਗ ਲੈ ਕੇ ਆਉਣਾ
    """
    poster_url = None
    imdb_rating = "7.2"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            clean_title = urllib.parse.quote_plus(title)
            search_url = f"https://api.themoviedb.org/3/search/multi?api_key=15d2ea6d0dc1d476efbca3eba2b9abfb&query={clean_title}"
            if year: search_url += f"&year={year}"
                
            async with session.get(search_url, timeout=8) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results", [])
                    if results:
                        movie = results[0]
                        vote = movie.get("vote_average")
                        if vote and vote != 0: 
                            imdb_rating = str(round(vote, 1))
                        
                        # 🎯 ਪਹਿਲਾਂ ਲੈਂਡਸਕੇਪ (Backdrop) ਇਮੇਜ ਚੈੱਕ ਕਰਨੀ
                        if movie.get("backdrop_path"):
                            v_backdrop = f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
                            # Weserv API ਰਾਹੀਂ 16:9 ਲੈਂਡਸਕੇਪ ਰੇਸ਼ੋ ਵਿੱਚ ਰੀਸਾਈਜ਼ ਕਰਨਾ
                            poster_url = f"https://images.weserv.nl/?url={v_backdrop}&w=2560&h=1440&fit=cover"
                        elif movie.get("poster_path"):
                            v_poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                            # ਜੇਕਰ ਸਿਰਫ਼ ਪੋਰਟਰੇਟ ਪੋਸਟਰ ਮਿਲੇ, ਤਾਂ ਉਸਨੂੰ ਲੈਂਡਸਕੇਪ ਬੈਕਗ੍ਰਾਊਂਡ ਵਿੱਚ ਫਿੱਟ ਕਰਨਾ
                            poster_url = f"https://images.weserv.nl/?url={v_poster}&w=2560&h=1440&fit=contain&bg=black"
        except Exception as e:
            logger.error(f"TMDB Fetch Error: {e}")

    if not poster_url:
        # ਡਿਫਾਲਟ ਸੁੰਦਰ ਲੈਂਡਸਕੇਪ ਸਿਨੇਮਾ ਬੈਕਗ੍ਰਾਊਂਡ
        poster_url = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=2560&h=1440&fit=crop"
    return poster_url, imdb_rating

# ਚੈਨਲ ਵਿੱਚ ਆਉਣ ਵਾਲੀਆਂ ਫਾਈਲਾਂ ਨੂੰ ਕੈਚ (Catch) ਕਰਨਾ
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def channel_post_handler(bot: Client, message: Message):
    movie_unique_key = None
    photo_to_send = None
    local_photo_path = f"poster_{message.id}.jpg"
    
    try:
        media_file = message.document or message.video or message.audio
        if not media_file: return

        # ਫਾਈਲ ਨੂੰ ਡਾਟਾਬੇਸ ਵਿੱਚ ਸੇਵ ਕਰਨਾ
        try: await save_file(message)
        except: pass

        file_name = getattr(media_file, "file_name", "movie.mp4") or "movie.mp4"
        title, year, audios, is_org = clean_movie_title(file_name)

        # ਇੱਕੋ ਮੂਵੀ ਦੀਆਂ ਬਾਰ-ਬਾਰ ਪੋਸਟਾਂ ਰੋਕਣ ਲਈ ਚੈੱਕ
        movie_unique_key = f"{title.lower()}_{year}"
        if movie_unique_key in POSTED_MOVIES: return
        POSTED_MOVIES.add(movie_unique_key)

        # ਡਾਟਾ ਫੈੱਚ ਕਰਨਾ
        poster_url, imdb_rating = await fetch_tmdb_data(title, year)

        # 🎬 ਤੁਹਾਡਾ ਮੰਗਿਆ ਹੋਇਆ ਸ਼ਾਰਟ ਫਾਰਮੈਟ
        year_str = f" ({year})" if year else ""
        audio_tags = " ".join([f"#{lang}" for lang in audios])
        if is_org: audio_tags += " #ORG"
            
        caption_text = (
            f"🎬 <code>{title}{year_str}</code>\n\n"
            f"⭐ <b>IMDb:</b> {imdb_rating}/10\n\n"
            f"📌 <i>(Touch To Copy)</i>\n\n"
            f"➡ <b>Audio Track:-</b> 🔊 {audio_tags}\n\n"
            f"<b>Added ✅</b>"
        )

        # ਬਟਨ ਸੈਟਿੰਗ (info.py ਮੁਤਾਬਕ)
        req_btn_text = f"🔰 {name} 🔰" if name else "🔰 JOIN MOVIE GROUP 🔰"
        req_url = GRP_LNK or "https://t.me/Moviesrequst01"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=req_btn_text, url=req_url)]])
        
        target_channel = MOVIE_UPDATE_CHANNEL

        # ਪੋਸਟਰ ਡਾਊਨਲোਡ ਕਰਨਾ
        if poster_url and poster_url.startswith("http"):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(poster_url, timeout=10) as resp:
                        if resp.status == 200:
                            with open(local_photo_path, "wb") as f:
                                f.write(await resp.read())
                            photo_to_send = local_photo_path
            except Exception as dl_err:
                logger.error(f"Poster Download Failed: {dl_err}")

        # ਜੇਕਰ ਆਨਲਾਈਨ ਪੋਸਟਰ ਫੇਲ ਹੋ ਜਾਵੇ ਤਾਂ ਫਾਈਲ ਦਾ ਆਪਣਾ ਥੰਬਨੇਲ ਵਰਤਣਾ
        if not photo_to_send and hasattr(media_file, "thumbs") and media_file.thumbs:
            try: photo_to_send = await bot.download_media(media_file.thumbs[0].file_id)
            except: photo_to_send = None

        # ਚੈਨਲ ਵਿੱਚ ਪੋਸਟ ਭੇਜਣਾ
        if photo_to_send and os.path.exists(str(photo_to_send)):
            try:
                await bot.send_photo(
                    chat_id=target_channel, 
                    photo=photo_to_send, 
                    caption=caption_text, 
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await bot.send_photo(chat_id=target_channel, photo=photo_to_send, caption=caption_text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
            except Exception:
                await bot.send_message(chat_id=target_channel, text=caption_text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)
        else:
            await bot.send_message(chat_id=target_channel, text=caption_text, reply_markup=reply_markup, parse_mode=enums.ParseMode.HTML)

    except Exception as grand_error:
        logger.error(f"Error in channel handler: {grand_error}")
        
    finally:
        # ਫਾਲਤੂ ਫਾਈਲਾਂ ਨੂੰ ਸਰਵਰ ਤੋਂ ਸਾਫ਼ ਕਰਨਾ
        if photo_to_send and not str(photo_to_send).startswith("http") and os.path.exists(str(photo_to_send)):
            try: os.remove(photo_to_send)
            except: pass
        elif os.path.exists(local_photo_path):
            try: os.remove(local_photo_path)
            except: pass
                
        # ਕੁਝ ਦੇਰ ਬਾਅਦ ਲਿਸਟ ਵਿੱਚੋਂ ਮੂਵੀ ਹਟਾਉਣੀ ਤਾਂ ਜੋ ਨਵੇਂ ਪ੍ਰਿੰਟ ਆਉਣ ਤੇ ਦੁਬਾਰਾ ਪੋਸਟ ਹੋ ਸਕੇ
        if movie_unique_key:
            await asyncio.sleep(15)
            POSTED_MOVIES.discard(movie_unique_key)
