# -*- coding: utf-8 -*-
"""
DreamxBotz - Complete Custom HD landscape Poster Generator Plugin
Place or replace this file at: /workspace/plugins/Dreamxfutures/Imdbposter.py
"""

import io
import re
import requests
import urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# 1. TMDB API Search - To find pristine landscape backdrops
def search_tmdb_backdrop_url(movie_title):
    try:
        # We use a public TMDB key. If you have your own, replace c22e0329ff01859b867c2688ca6a5e12
        search_query = urllib.parse.quote(movie_title)
        url = f"https://api.themoviedb.org/3/search/multi?api_key=c22e0329ff01859b867c2688ca6a5e12&query={search_query}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("results"):
                for item in data["results"]:
                    backdrop_path = item.get("backdrop_path")
                    if backdrop_path:
                        return f"https://image.tmdb.org/t/p/original{backdrop_path}"
    except Exception as e:
        print(f"[TMDB Backdrop Search Error]: {e}")
    return None


# 2. Google Image Search Scraper - As a robust fallback if TMDB doesn't return anything
def search_google_landscape_backdrop(movie_title):
    try:
        search_query = f"{movie_title} movie high resolution landscape backdrop wallpaper"
        url = "https://images.google.com/search?q=" + urllib.parse.quote(search_query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=10)
        # Search for high-resolution wallpaper links in Google search results
        links = re.findall(r'imgurl=(https?://[^&]+)', r.text)
        if links:
            return urllib.parse.unquote(links[0])
    except Exception as e:
        print(f"[Google Image Search Error]: {e}")
    return None


# 3. Cinematic Landscape Title Poster Creator using Pillow (PIL)
def generate_cinematic_title_poster(movie_title):
    W, H = 1280, 720
    img = None
    
    # Clean up title for searching (Remove formats, audio tracks, etc.)
    search_title = re.sub(r'\(?\b(1080p|720p|2160p|4k|HDR|WEB-DL|BluRay|NF|DS4K|Esub|H264|HEVC|10bit)\b\)?', '', movie_title, flags=re.IGNORECASE)
    search_title = search_title.replace(".", " ").replace("_", " ").strip()
    
    # A. Search TMDb first
    backdrop_url = search_tmdb_backdrop_url(search_title)
    
    # B. Download TMDB backdrop
    if backdrop_url:
        try:
            r = requests.get(backdrop_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content))
        except Exception as e:
            print(f"Error downloading TMDB backdrop: {e}")

    # C. Download Google Backdrop fallback if TMDB failed
    if img is None:
        google_url = search_google_landscape_backdrop(search_title)
        if google_url:
            try:
                r = requests.get(google_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content))
            except Exception as e:
                print(f"Error downloading Google backdrop: {e}")

    # D. Aspect Ratio Cropping & Resizing (Convert any image size to standard 16:9 widescreen)
    if img:
        img_w, img_h = img.size
        target_aspect = W / H
        curr_aspect = img_w / img_h
        
        if curr_aspect > target_aspect:
            # Image is wider, crop the left and right sides
            new_w = int(img_h * target_aspect)
            offset = (img_w - new_w) // 2
            img = img.crop((offset, 0, offset + new_w, img_h))
        else:
            # Image is taller, crop the top and bottom
            new_h = int(img_w / target_aspect)
            offset = (img_h - new_h) // 2
            img = img.crop((0, offset, img_w, offset + new_h))
            
        img = img.resize((W, H), Image.Resampling.LANCZOS)
    else:
        # Solid elegant Dark Cosmic slate background if no images found
        img = Image.new("RGB", (W, H), color="#08090e")

    draw = ImageDraw.Draw(img, "RGBA")

    # E. Draw left-to-right cinematic dark vignette overlay for high contrast text readability
    for x in range(W):
        if x < int(W * 0.75):
            opacity = int(220 * (1 - (x / (W * 0.75))))
            draw.rectangle([(x, 0), (x, H)], fill=(0, 0, 0, opacity))

    # F. Load clean bold sans-serif font
    # Clean the movie name for text rendering
    display_title = movie_title.upper().replace(".", " ").replace("_", " ")
    display_title = re.sub(r'\b(10BIT|HEVC|x265|x264|DDP5\.1|Atmos|WEB-DL|BluRay|Hindi|English|Dual-Audio)\b', '', display_title, flags=re.IGNORECASE)
    display_title = re.sub(r'\s+', ' ', display_title).strip()
    
    font = None
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except IOError:
        try:
            # Linux system fonts
            font = ImageFont.truetype("LiberationSans-Bold.ttf", 64)
        except IOError:
            # Fallback to PIL default font if everything else fails
            font = ImageFont.load_default()

    # G. Wrap Text to prevent overflow
    words = display_title.split()
    max_text_width = int(W * 0.7)
    spacing = 16  # Elegantly spaced letters (Tracking)
    
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        # Simple estimate of string width with wide spacing
        test_width = len(test_line) * 24 + (len(test_line) - 1) * spacing
        if test_width < max_text_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    # H. Render text lines on the image canvas
    font_height = 70
    total_text_height = len(lines) * (font_height * 1.3)
    start_y = (H - total_text_height) // 2 + 30
    start_x = int(W * 0.08)  # Left aligned spacing

    for line in lines:
        chars = list(line.upper())
        char_widths = []
        for char in chars:
            try:
                bbox = draw.textbbox((0, 0), char, font=font)
                w = bbox[2] - bbox[0] if bbox else 22
            except:
                w = 22
            char_widths.append(w)
            
        curr_x = start_x
        for idx, char in enumerate(chars):
            # 1. Subtle drop shadow for reading clarity on bright backgrounds
            draw.text((curr_x + 3, start_y + 3), char, fill=(0, 0, 0, 245), font=font)
            # 2. Cool light-blue slate title text (#BACDDB)
            draw.text((curr_x, start_y), char, fill=(186, 205, 219, 255), font=font)
            curr_x += char_widths[idx] + spacing
            
        start_y += int(font_height * 1.3)

    return img


# 4. Pyrogram bot event handler plugin definition
@Client.on_message(filters.command("poster") & filters.private)
async def poster_handler(bot: Client, message: Message):
    # Retrieve movie query from command argument
    query = message.text.split(" ", 1)
    if len(query) < 2:
        await message.reply_text("<b>ਕਿਰਪਾ ਕਰਕੇ ਮੂਵੀ ਦਾ ਨਾਮ ਲਿਖੋ! </b>\nExample: <code>/poster Pushpa 2</code>")
        return
        
    status_msg = await message.reply_text("🔍 Searching HD landscape backdrop and generating cinematic poster...")
    movie_name = query[1]

    try:
        # A. Create the high-quality PIL poster in RAM memory
        img = generate_cinematic_title_poster(movie_name)
        
        # B. Convert image to Bytes IO
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        
        # C. IMPORTANT CRITICAL FIX FOR PYROGRAM:
        # We MUST assign a file name to BytesIO object, otherwise Pyrogram will throw 'Invalid File' error!
        img_bytes.name = "poster.jpg"

        # D. Custom caption
        custom_caption = (
            f"<b>🎬 {movie_name.upper()}</b>\n\n"
            f"<b>⚜️ Powered By : <a href='https://t.me/dreamxbotz'>[ ᴅʀᴇᴀᴍxʙᴏᴛᴢ ]</a></b>"
        )
        
        # Simulated Inline Buttons
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Join Channel", url="https://t.me/dreamxbotz")]
        ])

        # E. Send photo successfully to chat
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=img_bytes,
            caption=custom_caption,
            reply_markup=keyboard
        )
        await status_msg.delete()

    except Exception as e:
        print(f"Error: {e}")
        await status_msg.edit_text(f"❌ Failed to generate poster: {e}")


# 5. Core integration function for your channel/indexing posts
# Call this function inside your post handler (e.g., post_handler.py or plugins/channel.py)
async def send_cinematic_post(bot: Client, chat_id: int, movie_title: str, caption: str, reply_markup=None):
    try:
        # Generate poster
        img = generate_cinematic_title_poster(movie_title)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        img_bytes.name = "poster.jpg" # Fixed name

        await bot.send_photo(
            chat_id=chat_id,
            photo=img_bytes,
            caption=caption,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Failed to post to channel: {e}")
        # Send raw text fallback
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup
        )
