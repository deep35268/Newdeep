import re
import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# info.py ਤੋਂ ਸਾਰੀਆਂ ਸੈਟਿੰਗਾਂ ਨੂੰ ਇੰਪੋਰਟ ਕਰਨਾ
from info import (
    CHANNELS, 
    MOVIE_UPDATE_CHANNEL, 
    TMDB_API_KEY, 
    IMDB_TEMPLATE, 
    GRP_LNK, 
    name
)

# ਡਾਟਾਬੇਸ ਫੰਕਸ਼ਨ ਸੇਫਲੀ ਇੰਪੋਰਟ ਕਰਨਾ
try:
    from database.ia_filterdb import save_file
except ImportError:
    try:
        from database.ia_filterdb import Alpha as save_file
    except ImportError:
        def save_file(*args, **kwargs): pass

POSTED_MOVIES = set()

QUALITY_KEYWORDS = ["2160p", "1080p", "720p", "480p", "360p", "4k", "uhd", "bluray", "web-dl", "webdl", "webrip", "hdrip", "brrip", "dvdrip", "hdtv", "x264", "x265", "hevc"]
AUDIO_PATTERNS = {"hindi": "Hindi", "english": "English", "eng": "English", "tamil": "Tamil", "telugu": "Telugu", "punjabi": "Punjabi", "dual": "Dual Audio", "multi": "Multi Audio"}

def clean_movie_title(filename: str):
    """
    ਸੁਪਰ ਐਡਵਾਂਸਡ ਫਿਲਟਰ: ਇਹ ਫਾਈਲ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਹਰ ਤਰ੍ਹਾਂ ਦੇ ਯੂਜ਼ਰਨੇਮ, ਲਿੰਕ ਅਤੇ ਕੂੜਾ ਸਾਫ਼ ਕਰਦਾ ਹੈ
    ਤਾਂ ਕਿ TMDB ਸਰਵਰ ਫਿਲਮ ਨੂੰ 1 ਸੈਕੰਡ ਵਿੱਚ ਪਛਾਣ ਸਕੇ।
    """
    name_str = str(filename)
    name_str = re.sub(r"\.(mkv|mp4|avi|webm|mov)$", "", name_str, flags=re.IGNORECASE)
    name_str = re.sub(r"@[\w_]+", " ", name_str)
    name_str = re.sub(r"https?://\S+", " ", name_str)
    name_str = re.sub(r"\[.*?\]|\(.*?\)", " ", name_str)
    name_str = name_str.replace(".", " ").replace("_", " ").replace("-", " ")
    
    found_audios = []
    name_lower = name_str.lower()
    for key, val in AUDIO_PATTERNS.items():
        if re.search(rf"\b{key}\b", name_lower):
            if val not in found_audios: found_audios.append(val)
    if not found_audios: found_audios = ["Hindi"]
    
    is_org = bool(re.search(r"\b(org|original)\b", name_lower))
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name_str)
    year = year_match.group(1) if year_match else ""
    
    cutoff = len(name_str)
    if year_match: cutoff = min(cutoff, year_match.start())
    for kw in QUALITY_KEYWORDS:
        match = re.search(rf"\b{kw}\b", name_lower)
        if match: cutoff = min(cutoff, match.start())
            
    clean_title = name_str[:cutoff].strip()
    if not clean_title: clean_title = name_str.strip()
    return re.sub(r"\s+", " ", clean_title).strip(), year, found_audios, is_org

async def fetch_tmdb_data(title: str, year: str):
    """
    info.py ਦੀ TMDB_API_KEY ਵਰਤ ਕੇ 100% ਅਸਲੀ HD Landscape ਪੋਸਟਰ ਅਤੇ ਰੇਟਿੰਗ ਲੱਭਣਾ
    """
    poster_url = None
    imdb_rating = "7.5" # ਡਿਫੌਲਟ ਬੈਕਅੱਪ ਰੇਟਿੰਗ
    
    async with aiohttp.ClientSession() as session:
        try:
            # info.py ਵਾਲੀ API Key ਦੀ ਵਰਤੋਂ
            api_key = TMDB_API_KEY or "15d2ea6d0dc1d476efbca3eba2b9abfb"
            search_url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={title.replace(' ', '+')}"
            if year:
                search_url += f"&year={year}"
                
            async with session.get(search_url, timeout=6) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results", [])
                    if results:
                        movie = results[0]
                        
                        # 1. 100% HD Landscape (Backdrop) ਪੋਸਟਰ ਚੁੱਕਣਾ
                        if movie.get("backdrop_path"):
                            poster_url = f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
                        elif movie.get("poster_path"):
                            # ਜੇਕਰ Landscape ਬੈਨਰ ਨਾ ਹੋਵੇ, ਤਾਂ ਵਰਟੀਕਲ ਪੋਸਟਰ ਨੂੰ 16:9 ਬੈਨਰ ਵਿੱਚ ਫਿੱਟ ਕਰਨਾ
                            v_poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                            poster_url = f"https://images.weserv.nl/?url={v_poster}&w=1280&h=720&fit=contain&bg=black"
                        
                        # 2. ਅਸਲੀ ਰੇਟਿੰਗ ਕੱਢਣਾ
                        vote_average = movie.get("vote_average")
                        if vote_average and vote_average != 0:
                            imdb_rating = str(round(vote_average, 1))
        except Exception as e:
            print(f"TMDB Fetch Error in channel.py: {e}")

    return poster_url, imdb_rating

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def media(bot: Client, message: Message):
    media_file = message.document or message.video or message.audio
    if not media_file: return

    # ਫਾਈਲ ਨੂੰ ਆਟੋ-ਫਿਲਟਰ ਡਾਟਾਬੇਸ ਵਿੱਚ ਸੇਵ ਕਰਨਾ
    try: 
        await save_file(message)
    except Exception: 
        pass

    file_name = getattr(media_file, "file_name", "movie.mp4") or "movie.mp4"
    title, year, audios, is_org = clean_movie_title(file_name)

    # ਇੱਕੋ ਮੂਵੀ ਬਾਰ-ਬਾਰ ਪੋਸਟ ਹੋਣ ਤੋਂ ਰੋਕਣ ਲਈ (ਡੁਪਲੀਕੇਟ ਲਾਕ)
    movie_unique_key = f"{title.lower()}_{year}"
    if movie_unique_key in POSTED_MOVIES: return
    POSTED_MOVIES.add(movie_unique_key)

    # TMDB ਤੋਂ ਡਾਟਾ ਲੈ ਕੇ ਆਉਣਾ
    poster, imdb_rating = await fetch_tmdb_data(title, year)

    # info.py ਦੇ IMDB_TEMPLATE ਦੇ ਮੁਤਾਬਕ ਕੈਪਸ਼ਨ ਤਿਆਰ ਕਰਨਾ
    try:
        caption_text = IMDB_TEMPLATE.format(
            title=title,
            year=year if year else "",
            rating=imdb_rating
        )
    except Exception:
        # ਜੇਕਰ ਫਾਰਮੈਟਿੰਗ ਵਿੱਚ ਕੋਈ ਦਿੱਕਤ ਆਵੇ ਤਾਂ ਸੇਫਟੀ ਬੈਕਅੱਪ ਕੈਪਸ਼ਨ
        year_str = f" {year}" if year else ""
        caption_text = f"🎬 `<code>{title}{year_str}</code>`\n\n⭐ IMDb: {imdb_rating}/10\n\n📌 (Touch To Copy)\n\nAdded ✅"

    # info.py ਦੇ GRP_LNK ਅਤੇ name (DREAMXBOTZ) ਦੇ ਹਿਸਾਬ ਨਾਲ ਬਟਨ ਬਣਾਉਣਾ
    req_btn_text = f"🔰 {name} 🔰" if name else "🔰 JOIN MOVIE GROUP 🔰"
    req_url = GRP_LNK or "https://t.me/Moviesrequst01"
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=req_btn_text, url=req_url)]])
    
    # ਜੇਕਰ ਇੰਟਰਨੈੱਟ 'ਤੇ ਕੋਈ ਪੋਸਟਰ ਨਾ ਮਿਲੇ, ਤਾਂ ਹੀ ਫਾਈਲ ਦਾ ਆਪਣਾ ਥੰਬਨੇਲ ਲੱਗੇਗਾ
    if not poster:
        if hasattr(media_file, "thumbs") and media_file.thumbs:
            try: 
                poster = await bot.download_media(media_file.thumbs[0].file_id)
            except Exception: 
                poster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1280"
        else: 
            poster = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1280"

    # ਮੂਵੀ ਅਪਡੇਟ ਚੈਨਲ ਉੱਪਰ ਪੋਸਟ ਭੇਜਣਾ
    target_channel = MOVIE_UPDATE_CHANNEL or -1003752618894
    try:
        await bot.send_photo(
            chat_id=target_channel, 
            photo=poster, 
            caption=caption_text, 
            reply_markup=reply_markup
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await bot.send_photo(chat_id=target_channel, photo=poster, caption=caption_text, reply_markup=reply_markup)
    except Exception as e:
        print(f"Channel Send Photo Error: {e}")
    finally:
        # ਡਾਊਨਲੋਡ ਕੀਤੀ ਹੋਈ ਫਾਈਲ ਸਥਾਨਕ ਸਟੋਰੇਜ ਵਿੱਚੋਂ ਸਾਫ਼ ਕਰਨਾ
        if poster and not poster.startswith("http") and os.path.exists(poster):
            try: os.remove(poster)
            except Exception: pass

    # ਲਾਕ ਖੋਲ੍ਹਣ ਲਈ ਟਾਈਮਰ
    await asyncio.sleep(10)
    POSTED_MOVIES.discard(movie_unique_key)
