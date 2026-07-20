import io
import re
import requests
import urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import Client, filters
from pyrogram.types import Message

# 1. ਗੂਗਲ ਇਮੇਜ ਤੋਂ HD ਲੈਂਡਸਕੇਪ ਬੈਕਡ੍ਰੌਪ ਲੱਭਣ ਲਈ ਸਕ੍ਰੈਪਰ (Google Search Backup)
def search_google_landscape_backdrop(movie_title):
    try:
        # ਵਧੀਆ ਕੁਆਲਿਟੀ ਵਾਲੇ ਵਾਲਪੇਪਰ ਲਈ ਖੋਜ
        search_query = f"{movie_title} movie high resolution landscape backdrop wallpaper"
        url = "https://images.google.com/search?q=" + urllib.parse.quote(search_query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        # ਇਮੇਜ ਦੇ ਸਿੱਧੇ ਲਿੰਕਸ ਫਾਈਂਡ ਕਰਨ ਲਈ ਰੇਜੈਕਸ (Regex)
        links = re.findall(r'imgurl=(https?://[^&]+)', response.text)
        if links:
            return urllib.parse.unquote(links[0])
    except Exception as e:
        print(f"[!] Google Image Search Error: {e}")
    return None

# 2. TMDb API ਰਾਹੀਂ ਲੈਂਡਸਕੇਪ ਬੈਕਡ੍ਰੌਪ ਲੱਭਣ ਵਾਲਾ ਫੰਕਸ਼ਨ
def search_tmdb_backdrop_url(movie_title):
    try:
        search_query = urllib.parse.quote(movie_title)
        # TMDb ਸਰਚ URL
        url = f"https://api.themoviedb.org/3/search/multi?api_key=c22e0329ff01859b867c2688ca6a5e12&query={search_query}"
        r = requests.get(url, timeout=10).json()
        if r.get("results"):
            item = r["results"][0]
            backdrop_path = item.get("backdrop_path")
            if backdrop_path:
                return f"https://image.tmdb.org/t/p/original{backdrop_path}"
    except Exception as e:
        print(f"[!] TMDb API Error: {e}")
    return None

# 3. ਫਿਲਮ ਦੇ ਨਾਮ ਅਤੇ ਬੈਕਡ੍ਰੌਪ ਇਮੇਜ ਤੋਂ ਸਿਨੇਮੈਟਿਕ 16:9 ਪੋਸਟਰ ਬਣਾਉਣ ਵਾਲਾ ਫੰਕਸ਼ਨ
def generate_cinematic_landscape_poster(movie_title, backdrop_url=None):
    W, H = 1280, 720  # Perfect 16:9 HD Resolution
    img = None
    
    # ਪਹਿਲਾਂ TMDb ਲਿੰਕ ਨੂੰ ਡਾਊਨਲੋਡ ਕਰਨ ਦੀ ਕੋਸ਼ਿਸ਼ ਕਰੋ
    if backdrop_url:
        try:
            r = requests.get(backdrop_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content))
        except Exception as e:
            print(f"[-] TMDb Backdrop download failed: {e}")

    # ਜੇ TMDb ਫੇਲ ਹੋਵੇ ਜਾਂ ਖਾਲੀ ਹੋਵੇ, ਤਾਂ ਗੂਗਲ ਤੋਂ ਸਰਚ ਕਰਕੇ ਵਾਲਪੇਪਰ ਲਿਆਓ!
    if img is None:
        print(f"[+] Searching google for backdrop of: {movie_title}")
        google_url = search_google_landscape_backdrop(movie_title)
        if google_url:
            try:
                r = requests.get(google_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content))
            except Exception as e:
                print(f"[-] Google backdrop download failed: {e}")

    # ਜੇਕਰ ਕੋਈ ਵੀ ਫੋਟੋ ਨਾ ਮਿਲੇ, ਤਾਂ ਇੱਕ ਬਹੁਤ ਹੀ ਸੁੰਦਰ ਡਾਰਕ ਗ੍ਰੇਡੀਐਂਟ ਬੈਕਗਰਾਊਂਡ ਤਿਆਰ ਕਰੋ
    if img:
        # ਫੋਟੋ ਨੂੰ 16:9 ਰੇਸ਼ੋ ਵਿੱਚ ਬਰਾਬਰ ਕੱਟੋ (Crop & Center Resize)
        img_w, img_h = img.size
        target_aspect = W / H
        curr_aspect = img_w / img_h
        
        if curr_aspect > target_aspect:
            new_w = int(img_h * target_aspect)
            offset = (img_w - new_w) // 2
            img = img.crop((offset, 0, offset + new_w, img_h))
        else:
            new_h = int(img_w / target_aspect)
            offset = (img_h - new_h) // 2
            img = img.crop((0, offset, img_w, offset + new_h))
            
        img = img.resize((W, H), Image.Resampling.LANCZOS)
    else:
        # ਖੂਬਸੂਰਤ ਡਾਰਕ ਸਲੇਟ ਬਲੈਕ ਗ੍ਰੇਡੀਐਂਟ
        img = Image.new("RGB", (W, H), color="#090a10")

    draw = ImageDraw.Draw(img, "RGBA")

    # 4. ਸਿਨੇਮੈਟਿਕ ਵਾਈਨੈੱਟ (Vignette) - ਖੱਬੇ ਤੋਂ ਸੱਜੇ ਕਾਲਾ ਸ਼ੇਡ ਓਵਰਲੇਅ 
    # ਇਹ ਟੈਕਸਟ (ਲਿਖਾਈ) ਨੂੰ 100% ਸਾਫ ਅਤੇ ਪੜ੍ਹਨਯੋਗ ਬਣਾਉਂਦਾ ਹੈ, ਭਾਵੇਂ ਬੈਕਗਰਾਊਂਡ ਚਿੱਟਾ ਹੋਵੇ
    for x in range(W):
        if x < int(W * 0.75):
            opacity = int(215 * (1 - (x / (W * 0.75))))
            draw.rectangle([(x, 0), (x, H)], fill=(0, 0, 0, opacity))

    # ਟਾਈਟਲ ਨੂੰ ਸਾਫ਼ ਕਰੋ (ਜਿਵੇਂ 10bit, x265 ਆਦਿ ਹਟਾਉਣਾ)
    clean_title = movie_title.upper().replace("10BIT", "").strip()
    words = clean_title.split()
    
    # ਫੋਂਟ ਸੈੱਟਅੱਪ (ਸਿਸਟਮ ਫੋਂਟ ਵਰਤੋਂ, ਨਹੀਂ ਤਾਂ ਡਿਫੌਲਟ ਫੋਂਟ)
    font = None
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except IOError:
        try:
            font = ImageFont.truetype("LiberationSans-Bold.ttf", 64)
        except IOError:
            font = ImageFont.load_default()

    # 5. ਅੱਖਰਾਂ ਦੇ ਵਿਚਕਾਰ ਖੂਬਸੂਰਤ ਸਿਨੇਮੈਟਿਕ ਸਪੇਸਿੰਗ (Letter Spacing: 16px)
    spacing = 16
    max_text_width = int(W * 0.72)
    
    # ਲਾਈਨ ਰੈਪਿੰਗ (ਜੇ ਮੂਵੀ ਦਾ ਨਾਮ ਵੱਡਾ ਹੈ ਤਾਂ ਆਟੋਮੈਟਿਕ ਅਗਲੀ ਲਾਈਨ ਵਿੱਚ ਜਾਵੇਗਾ)
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        chars = list(test_line)
        test_width = sum([25 for _ in chars]) + (len(chars) - 1) * spacing
        if test_width < max_text_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    # ਲਿਖਾਈ ਨੂੰ ਪੋਸਟਰ ਦੇ ਖੱਬੇ ਪਾਸੇ (Left side) ਸੈਂਟਰ ਕਰਕੇ ਡਰਾਅ ਕਰਨਾ
    font_height = 70
    total_text_height = len(lines) * (font_height * 1.3)
    start_y = (H - total_text_height) // 2 + 30
    start_x = int(W * 0.08)

    for line in lines:
        chars = list(line.upper())
        char_widths = []
        for char in chars:
            try:
                bbox = draw.textbbox((0, 0), char, font=font)
                w = bbox[2] - bbox[0] if bbox else 24
            except:
                w = 24
            char_widths.append(w)
            
        curr_x = start_x
        for idx, char in enumerate(chars):
            # ਏਲੀਅਨ 3D ਡ੍ਰੌਪ ਸ਼ੈਡੋ (High-contrast shadow)
            draw.text((curr_x + 3, start_y + 3), char, fill=(0, 0, 0, 245), font=font)
            # ਅਸਲੀ ਅੱਖਰ (Elegant Light Steel Blue #BACDDB)
            draw.text((curr_x, start_y), char, fill=(186, 205, 219, 255), font=font)
            curr_x += char_widths[idx] + spacing
            
        start_y += int(font_height * 1.3)

    return img

# 6. ਪਾਈਰੋਗ੍ਰਾਮ ਬੋਟ ਫੰਕਸ਼ਨ (Pyrogram Post Event Handler)
async def post_movie_with_generated_poster(bot, message, movie_title, backdrop_url=None, caption="", reply_markup=None):
    # ਜੇਕਰ ਕੋਈ ਪੋਸਟਰ ਯੂਆਰਐਲ ਨਹੀਂ ਦਿੱਤਾ, ਤਾਂ ਪਹਿਲਾਂ TMDb ਚੈੱਕ ਕਰੋ
    if not backdrop_url:
        backdrop_url = search_tmdb_backdrop_url(movie_title)
        
    # ਰੈਮ (RAM Memory) ਵਿੱਚ ਪੋਸਟਰ ਇਮੇਜ ਤਿਆਰ ਕਰੋ
    img = generate_cinematic_landscape_poster(movie_title, backdrop_url)
    
    # ਇਮੇਜ ਨੂੰ ਬਾਈਟਸ (Bytes IO) ਵਿੱਚ ਸੇਵ ਕਰੋ
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=95)
    img_bytes.seek(0)
    
    # ==========================================================
    # ⚠️ CRITICAL BUG FIX (ਇਸ ਨਾਲ 'Send Photo Error' ਪੂਰੀ ਤਰ੍ਹਾਂ ਹੱਲ ਹੋਵੇਗਾ):
    # Pyrogram ਨੂੰ ਦੱਸਣਾ ਪੈਂਦਾ ਹੈ ਕਿ ਇਹ ਇੱਕ ਫਾਈਲ ਹੈ, ਇਸ ਲਈ ਨਾਮ 'poster.jpg' ਸੈੱਟ ਕੀਤਾ ਹੈ।
    # ==========================================================
    img_bytes.name = "poster.jpg"

    # ਪੋਸਟਰ ਨੂੰ ਚੈਨਲ ਵਿੱਚ ਭੇਜੋ
    try:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=img_bytes,
            caption=caption,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"[!] Send Photo failed, sending caption text as fallback: {e}")
        # ਜੇ ਫੋਟੋ ਭੇਜਣ ਵਿੱਚ ਕੋਈ ਦਿੱਕਤ ਆਵੇ ਤਾਂ ਟੈਕਸਟ ਸੁਨੇਹਾ ਭੇਜੋ
        await bot.send_message(
            chat_id=message.chat.id,
            text=caption,
            reply_markup=reply_markup
    )
