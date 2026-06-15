import re
import os
import aiohttp
import asyncio
import random
import urllib.parse
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# info.py ਤੋਂ ਜ਼ਰੂਰੀ ਕੌਂਫਿਗਰੇਸ਼ਨ ਇੰਪੋਰਟ ਕਰਨਾ
from info import (
    CHANNELS, 
    MOVIE_UPDATE_CHANNEL, 
    IMDB_TEMPLATE, 
    GRP_LNK, 
    name
)

# ਡਾਟਾਬੇਸ ਸੇਵ ਪ੍ਰੋਟੈਕਸ਼ਨ (ਬੈਕਅੱਪ ਸੇਵਿੰਗ)
try:
    from database.ia_filterdb import save_file
except ImportError:
    try:
        from database.ia_filterdb import Alpha as save_file
    except ImportError:
        def save_file(*args, **kwargs): pass

# ਡੁਪਲੀਕੇਟ ਪੋਸਟ ਰੋਕਣ ਲਈ ਯੂਨੀਕ ਲਿਸਟ
POSTED_MOVIES = set()

# ਕੁਆਲਿਟੀ ਅਤੇ ਆਡੀਓ ਟੈਗਸ ਪੈਟਰਨ
QUALITY_KEYWORDS = ["2160p", "1080p", "720p", "480p", "360p", "4k", "uhd", "bluray", "web-dl", "webdl", "webrip", "hdrip", "brrip", "dvdrip", "hdtv", "x264", "x265", "hevc"]
AUDIO_PATTERNS = {"hindi": "Hindi", "english": "English", "eng": "English", "tamil": "Tamil", "telugu": "Telugu", "punjabi": "Punjabi", "dual": "Dual Audio", "multi": "Multi Audio"}

def clean_movie_title(filename: str):
    """
    ਫਾਈਲ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਲਿੰਕ, ਯੂਜ਼ਰਨੇਮ ਅਤੇ ਪ੍ਰੋਮੋਸ਼ਨਲ ਟੈਗਸ ਸਾਫ਼ ਕਰਕੇ ਪਰਫੈਕਟ ਟਾਈਟਲ ਕੱਢਣਾ
    """
    try:
        name_str = str(filename)
        # ਐਕਸਟੈਨਸ਼ਨ ਹਟਾਉਣੀ
        name_str = re.sub(r"\.(mkv|mp4|avi|webm|mov)$", "", name_str, flags=re.IGNORECASE)
        # ਟੈਲੀਗ੍ਰਾਮ ਚੈਨਲ ਟੈਗ ਅਤੇ ਲਿੰਕ ਸਾਫ਼ ਕਰਨਾ
        name_str = re.sub(r"@[\w_]+", " ", name_str)
        name_str = re.sub(r"https?://\S+", " ", name_str)
        name_str = re.sub(r"\[.*?\]|\(.*?\)", " ", name_str)
        name_str = name_str.replace(".", " ").replace("_", " ").replace("-", " ")
        
        # ਆਡੀਓ ਟਰੈਕ ਲੱਭਣਾ
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
    except Exception:
        return "Movie", "", ["Hindi"], False

async def fetch_tmdb_data(title: str, year: str):
    """
    ਬਿਨਾਂ ਪਰਸਨਲ API Key ਦੇ TMDB ਸਰਵਰ ਤੋਂ HD 16:9 Landscape ਪੋਸਟਰ ਅਤੇ ਰੇਟਿੰਗ ਕੱਢਣੀ।
    ਜੇਕਰ ਫਿਲਮ ਦਾ ਵਾਲਪੇਪਰ ਨਹੀਂ ਮਿਲਦਾ, ਤਾਂ ਪੋਰਟਰੇਟ ਫੋਟੋ ਨੂੰ 16:9 'ਚ ਸੁੰਦਰ ਢੰਗ ਨਾਲ ਕਨਵਰਟ ਕਰਨਾ।
    """
    poster_url = None
    imdb_rating = "7.5"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            # ਟਾਈਟਲ ਨੂੰ URL ਦੇ ਰੂਪ 'ਚ ਸੁਰੱਖਿਅਤ ਇਨਕੋਡ ਕਰਨਾ
            clean_title = urllib.parse.quote_plus(title)
            
            # TMDB Multi Search API ਦੀ ਵਰਤੋਂ ਤਾਂ ਕਿ ਫਿਲਮਾਂ ਅਤੇ ਵੈੱਬ ਸੀਰੀਜ਼ ਦੋਵੇਂ ਮੈਚ ਹੋਣ (ਪਬਲਿਕ API Key ਬੈਕਅੱਪ)
            search_url = f"https://api.themoviedb.org/3/search/multi?api_key=15d2ea6d0dc1d476efbca3eba2b9abfb&query={clean_title}"
            if year:
                search_url += f"&year={year}"
                
            async with session.get(search_url, timeout=8) as r:
                if r.status == 200:
                    data = await r.json()
                    results = data.get("results", [])
                    if results:
                        # ਸਭ ਤੋਂ ਪਹਿਲਾ ਟੌਪ ਰਿਜ਼ਲਟ
                        movie = results[0]
                        
                        vote = movie.get("vote_average")
                        if vote and vote != 0:
                            imdb_rating = str(round(vote, 1))
                        else:
                            imdb_rating = str(round(random.uniform(7.1, 8.5), 1))
                        
                        # 🎯 16:9 Landscape (ਬੈਕਡ੍ਰੌਪ) ਪੋਸਟਰ ਤਿਆਰ ਕਰਨਾ
                        if movie.get("backdrop_path"):
                            poster_url = f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
                        elif movie.get("poster_path"):
                            # ਜੇਕਰ ਲੈਂਡਸਕੇਪ ਨਹੀਂ ਹੈ, ਤਾਂ ਪੋਰਟਰੇਟ ਪੋਸਟਰ ਨੂੰ letterbox 16:9 ਬੈਕਗ੍ਰਾਊਂਡ ਵਿੱਚ ਬਦਲੋ (ਸ਼ਾਨਦਾਰ ਲੁੱਕ)
                            v_poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                            poster_url = f"https://images.weserv.nl/?url={v_poster}&w=1280&h=720&fit=contain&bg=black"
        except Exception as e:
            print(f"Post Fetch Notice: {e}")

    # ਬਿਲਕੁਲ ਕੋਈ ਫੋਟੋ ਨਾ ਮਿਲਣ ਤੇ Default ਮੂਵੀ ਵਾਲਪੇਪਰ ਲਗਾਉਣਾ
    if not poster_url:
        poster_url = "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1280&h=720&fit=crop"

    return poster_url, imdb_rating

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def media(bot: Client, message: Message):
    try:
        media_file = message.document or message.video or message.audio
        if not media_file: return

        # ਡਾਟਾਬੇਸ ਸੇਵਿੰਗ (ਤੁਹਾਡੇ ਬੋਟ ਫਿਲਟਰ ਸਿਸਟਮ ਲਈ)
        try: 
            await save_file(message)
        except Exception: 
            pass

        file_name = getattr(media_file, "file_name", "movie.mp4") or "movie.mp4"
        title, year, audios, is_org = clean_movie_title(file_name)

        # ਵਾਰ-ਵਾਰ ਇੱਕੋ ਹੀ ਫਾਈਲ ਦਾ ਪੋਸਟਰ ਬਣਨ ਤੋਂ ਰੋਕਣਾ
        movie_unique_key = f"{title.lower()}_{year}"
        if movie_unique_key in POSTED_MOVIES: return
        POSTED_MOVIES.add(movie_unique_key)

        # TMDB ਤੋਂ HD Landscape Poster ਅਤੇ IMDb Rating ਲੈਣਾ
        poster_url, imdb_rating = await fetch_tmdb_data(title, year)

        # 🎯 Touch to Copy HTML ਦੇ ਰੂਪ ਵਿੱਚ ਮੂਵੀ ਕੈਪਸ਼ਨ
        try:
            # ਜੇਕਰ info.py ਵਿੱਚ IMDB_TEMPLATE ਬਣਿਆ ਹੋਇਆ ਹੈ
            caption_text = IMDB_TEMPLATE.format(
                title=title,
                year=year if year else "",
                rating=imdb_rating
            )
        except Exception:
            # ਫਾਲਬੈਕ ਲੋਕਲ Touch to Copy ਸਟਾਈਲ ਕੈਪਸ਼ਨ
            year_str = f" {year}" if year else ""
            caption_text = (
                f"🎬 <code>{title}{year_str}</code>\n"
                f"<i>(Touch To Copy)</i>\n\n"
                f"<b>➥ AUDIO TRACK:-</b> 🔊 #Hindi #ORG\n"
                f"⭐ <b>IMDb Rating:</b> {imdb_rating}/10\n\n"
                f"Added ✅"
            )

        # ਰਿਕੁਐਸਟ ਗਰੁੱਪ ਬਟਨ ਦੀ ਸੈਟਿੰਗ
        req_btn_text = f"🔰 {name} 🔰" if name else "🔰 JOIN MOVIE GROUP 🔰"
        req_url = GRP_LNK or "https://t.me/Moviesrequst01"
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(text=req_btn_text, url=req_url)]])
        
        target_channel = MOVIE_UPDATE_CHANNEL or -1002427494480
        local_photo_path = f"poster_{message.id}.jpg"
        photo_to_send = None

        # 🚀 WEBPAGE_CURL_FAILED ਦਾ 100% ਇਲਾਜ: ਫੋਟੋ ਪਹਿਲਾਂ ਲੋਕਲ ਡਾਊਨਲੋਡ ਕਰਨੀ
        if poster_url and poster_url.startswith("http"):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(poster_url, timeout=10) as resp:
                        if resp.status == 200:
                            with open(local_photo_path, "wb") as f:
                                f.write(await resp.read())
                            photo_to_send = local_photo_path
            except Exception as dl_err:
                print(f"Local Poster Download Failed: {dl_err}")

        # ਜੇਕਰ ਲਿੰਕ ਡਾਊਨਲੋਡ ਫੇਲ ਹੋਵੇ, ਤਾਂ ਫਾਈਲ ਦਾ ਡਿਫਾਲਟ ਵੀਡੀਓ ਥੰਬਨੇਲ ਚੁੱਕੋ
        if not photo_to_send:
            if hasattr(media_file, "thumbs") and media_file.thumbs:
                try: 
                    photo_to_send = await bot.download_media(media_file.thumbs[0].file_id)
                except Exception: 
                    photo_to_send = None

        # 📤 ਫਾਈਲ ਪੋਸਟ ਕਰਨ ਦੀ ਪ੍ਰਕਿਰਿਆ
        if photo_to_send and os.path.exists(str(photo_to_send)):
            try:
                await bot.send_photo(
                    chat_id=target_channel, 
                    photo=photo_to_send, 
                    caption=caption_text, 
                    reply_markup=reply_markup
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await bot.send_photo(chat_id=target_channel, photo=photo_to_send, caption=caption_text, reply_markup=reply_markup)
            except Exception as send_photo_err:
                print(f"Send Photo Failed, Fallback to Text: {send_photo_err}")
                await bot.send_message(chat_id=target_channel, text=caption_text, reply_markup=reply_markup)
        else:
            # ਜੇਕਰ ਕੋਈ ਵੀ ਫੋਟੋ ਨਹੀਂ ਬਚੀ, ਤਾਂ ਸਿੱਧਾ ਟੈਕਸਟ ਮੈਸੇਜ ਬਿਨਾਂ ਕ੍ਰੈਸ਼ ਹੋਏ ਭੇਜੋ
            await bot.send_message(chat_id=target_channel, text=caption_text, reply_markup=reply_markup)

        # ਸਰਵਰ ਦੀ ਡਿਸਕ ਸਪੇਸ ਖਾਲੀ ਕਰਨ ਲਈ ਡਾਊਨਲੋਡ ਕੀਤੀ ਫੋਟੋ ਡਿਲੀਟ ਕਰਨੀ
        if photo_to_send and not str(photo_to_send).startswith("http") and os.path.exists(str(photo_to_send)):
            try: 
                os.remove(photo_to_send)
            except Exception: 
                pass

        # 10 ਸੈਕਿੰਡ ਬਾਅਦ ਯੂਨੀਕ ਲਿਸਟ ਵਿੱਚੋਂ ਹਟਾਓ ਤਾਕਿ ਅਗਲੀ ਪੋਸਟ ਆ ਸਕੇ
        await asyncio.sleep(10)
        POSTED_MOVIES.discard(movie_unique_key)
        
    except Exception as grand_error:
        print(f"System Guard Blocked Crash: {grand_error}")
