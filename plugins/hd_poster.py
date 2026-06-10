import re
import requests
from pyrogram import Client, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 1. 💾 ਡੁਪਲੀਕੇਟ ਪੋਸਟਾਂ ਨੂੰ ਰੋਕਣ ਲਈ ਮੈਮੋਰੀ ਕੈਸ਼ (In-Memory Movie Lock Cache)
POSTED_MOVIES_CACHE = set()

def get_hd_widescreen_poster(title: str, tmdb_api_key: str):
    """
    TMDB API ਤੋਂ ਮੂਵੀ ਸਰਚ ਕਰਕੇ widescreen 'backdrop_path' (16:9) ਐਚਡੀ ਲਿੰਕ ਵਾਪਸ ਕਰਦਾ ਹੈ।
    ਜੇਕਰ backdrop ਉਪਲਬਧ ਨਹੀਂ ਹੈ, ਤਾਂ 'w1280' ਰੈਜ਼ੋਲਿਊਸ਼ਨ ਵਾਲੇ poster_path ਨੂੰ ਚੁਣਦਾ ਹੈ।
    """
    try:
        # ਫਿਲਟਰੀਕਰਨ: ਮੂਵੀ ਦੇ ਨਾਮ ਵਿੱਚੋਂ ਫਾਲਤੂ 720p/1080p ਸ਼ਬਦ ਹਟਾਉਂਦਾ ਹੈ
        clean_title = re.sub(r'\s\d+p|\s[hH][dD]|\s[wW][eE][bB]\-[dD][lL]', '', title).strip()
        url = f"https://api.themoviedb.org/3/search/movie?api_key={tmdb_api_key}&query={clean_title}"
        
        response = requests.get(url, timeout=10).json()
        if response.get('results'):
            movie = response['results'][0]
            backdrop = movie.get('backdrop_path')
            poster = movie.get('poster_path')
            
            # ਬਿਲਕੁਲ ਸਾਫ਼ ਅਤੇ ਐਚਡੀ (w1280) ਫੋਟੋ ਲਿੰਕ ਤਿਆਰ ਕਰਨਾ
            if backdrop:
                return f"https://image.tmdb.org/t/p/w1280{backdrop}"
            elif poster:
                return f"https://image.tmdb.org/t/p/w1280{poster}"
    except Exception as e:
        print(f"[TMDB HD Retriever Error] {e}")
    return None

async def send_single_movie_hd_post(client: Client, chat_id: int, movie_title: str, movie_year: str, tmdb_api_key: str, group_link: str = "https://t.me/your_movie_group"):
    """
    ਇੱਕ ਫਿਲਮ ਦਾ ਸਿਰਫ਼ 1 ਹੀ HD ਪੋਸਟਰ ਚੈਨਲ ਵਿੱਚ ਭੇਜਦਾ ਹੈ। (One Poster Per Movie)
    ਕੈਪਸ਼ਨ ਅਤੇ ਬਟਨ ਬਿਲਕੁਲ ਤੁਹਾਡੇ ਦੁਆਰਾ ਭੇਜੇ ਗਏ ਸਕ੍ਰੀਨਸ਼ੌਟ ਵਰਗੇ ਹਨ!
    """
    global POSTED_MOVIES_CACHE
    
    # 🔍 ਡੁਪਲੀਕੇਟ ਪੋਸਟਰਾਂ ਤੋਂ ਬਚਣ ਲਈ ਯੂਨੀਕ ID ਤਿਆਰ ਕਰਨਾ
    movie_id = f"{movie_title.lower().strip()}_{movie_year}"
    
    if movie_id in POSTED_MOVIES_CACHE:
        print(f"[Duplicate Filter] {movie_title} ({movie_year}) ਪਹਿਲਾਂ ਹੀ ਚੈਨਲ ਵਿੱਚ ਪੋਸਟ ਹੈ! ਦੁਬਾਰਾ ਪੋਸਟਰ ਨਹੀਂ ਭੇਜਿਆ ਜਾਵੇਗਾ।")
        return False
        
    # 📸 TMDB ਤੋਂ HD ਬੈਕਡ੍ਰੌਪ ਪੋਸਟਰ ਲਿਆਉਣਾ
    poster_url = get_hd_widescreen_poster(movie_title, tmdb_api_key)
    
    # ਜੇਕਰ TMDB ਕੰਮ ਨਾ ਕਰੇ, ਤਾਂ ਡਿਫੌਲਟ ਬੈਕਅੱਪ ਫੋਟੋ
    if not poster_url:
        poster_url = "https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&q=80&w=1280"
        
    # ✍️ ਕੈਪਸ਼ਨ ਦਾ ਡਿਜ਼ਾਈਨ: ਸਕ੍ਰੀਨਸ਼ੌਟ ਵਾਂਗ ਸੇਮ ਟੂ ਸੇਮ (<code> ਟੈਗ ਲਗਾਇਆ ਹੈ ਤਾਂ ਜੋ ਟੱਚ-ਟੂ-ਕਾਪੀ ਹੋ ਸਕੇ)
    caption_text = f"<code>{movie_title} {movie_year}\n(Touch To Copy)</code>\n\n<b>➥ AUDIO TRACK:- 🔊 #Hindi #ORG</b>\n\nAdded ✅"
    
    # 🎬 ਇਨਲਾਈਨ ਬਟਨ: ਸੇਮ ਟੂ ਸੇਮ (Inline Markup Keyboard Button)
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Movie Request Group 🎬", url=group_link)]
    ])
    
    try:
        # 🚀 ਚੈਨਲ ਵਿੱਚ ਫੋਟੋ, ਕੈਪਸ਼ਨ ਅਤੇ ਬਟਨ ਅਪਲੋਡ ਕਰਨਾ
        await client.send_photo(
            chat_id=chat_id,
            photo=poster_url,
            caption=caption_text,
            parse_mode=enums.ParseMode.HTML,  # ਬਹੁਤ ਮਹੱਤਵਪੂਰਨ: ਇਸ ਨਾਲ ਟੱਚ-ਟੂ-ਕਾਪੀ ਚਾਲੂ ਹੋਵੇਗਾ!
            reply_markup=reply_markup
        )
        
        # 💾 ਕੈਸ਼ ਵਿੱਚ ਸੇਵ ਕਰ ਲਵੋ ਤਾਂ ਜੋ ਅਗਲੀ ਵਾਰ ਡੁਪਲੀਕੇਟ ਹੋਣ 'ਤੇ ਫਿਲਟਰ ਹੋ ਸਕੇ
        POSTED_MOVIES_CACHE.add(movie_id)
        print(f"[Success] Beautiful widescreen HD poster sent for: {movie_title} ({movie_year})")
        return True
    except Exception as e:
        print(f"[Pyrogram Posting Failed] {e}")
        return False
