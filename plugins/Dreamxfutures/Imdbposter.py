import io
import re
import requests
import urllib.parse
from PIL import Image, ImageDraw, ImageFont
from pyrogram import Client, filters
from pyrogram.types import Message

# Import TMDb key if present in bot info configurations
try:
    from info import TMDB_API_KEY
except ImportError:
    TMDB_API_KEY = "c22e0329ff01859b867c2688ca6a5e12" # Public default fallback key

# Custom dict helper class supporting BOTH dictionary style (d['title']) and property style (d.title) access
class MovieInfo(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for k, v in self.items():
            setattr(self, k, v)
            
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
            
    def __setattr__(self, name, value):
        self[name] = value
        super().__setattr__(name, value)

# Search multi (movies & tv shows) on TMDb
def search_tmdb(query):
    try:
        api_key = TMDB_API_KEY if TMDB_API_KEY else "c22e0329ff01859b867c2688ca6a5e12"
        search_query = urllib.parse.quote(query)
        url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={search_query}"
        r = requests.get(url, timeout=10).json()
        if r.get("results"):
            results = [x for x in r["results"] if x.get("media_type") in ["movie", "tv"]]
            if results:
                return results[0]
    except Exception as e:
        print(f"TMDb Search Error: {e}")
    return None

# Fetch complete movie/series details from TMDb and return MovieInfo
async def get_movie_details(query):
    # Clean file name parameters to make TMDb query accurate
    clean_query = query
    clean_query = re.sub(r'\(?\b(19|20)\d{2}\b\)?', '', clean_query)
    clean_query = re.sub(r'\b(1080p|720p|2160p|4k|hdr|web-dl|nf|webrip|h264|x264|x265|hevc|ddp5\.1|dual-audio|hindi|english|tamil|telugu|bengali|malayalam|punjabi|mkv|mp4)\b.*', '', clean_query, flags=re.IGNORECASE)
    clean_query = clean_query.replace('.', ' ').replace('_', ' ').strip()
    
    if not clean_query:
        clean_query = query

    item = search_tmdb(clean_query)
    if not item:
        # Solid backup in case of no results on TMDb
        return MovieInfo(
            title=query.replace('.', ' ').replace('_', ' ').strip().upper(),
            year="N/A",
            rating="N/A",
            genres="Action, Drama",
            poster="",
            plot="No overview found.",
            director="N/A",
            cast=[],
            runtime="N/A",
            votes="N/A",
            languages="Hindi",
            backdrop="",
            backdrop_url="",
            poster_url="",
            ott_platform="N/A",
            quality="1080p WEB-DL",
            type="movie"
        )
        
    api_key = TMDB_API_KEY if TMDB_API_KEY else "c22e0329ff01859b867c2688ca6a5e12"
    media_id = item["id"]
    media_type = item["media_type"]
    
    try:
        url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={api_key}&append_to_response=credits"
        details = requests.get(url, timeout=10).json()
    except Exception:
        details = item

    title = details.get("title") or details.get("name") or details.get("original_title") or "N/A"
    release_date = details.get("release_date") or details.get("first_air_date") or ""
    year = release_date.split("-")[0] if release_date else "N/A"
    
    rating = str(details.get("vote_average", "N/A"))
    if rating != "N/A" and rating != "0" and rating != "0.0":
        rating = f"{float(rating):.1f}"
    else:
        rating = "7.0"
        
    genres_list = details.get("genres", [])
    genres = ", ".join([g["name"] for g in genres_list]) if genres_list else "Action, Drama"
    
    backdrop_path = details.get("backdrop_path")
    backdrop_url = f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else ""
    
    poster_path = details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else ""
    
    plot = details.get("overview") or "No overview found."
    
    cast_list = []
    director = "N/A"
    credits = details.get("credits", {})
    if credits:
        cast_list = [c["name"] for c in credits.get("cast", [])[:4]]
        for crew in credits.get("crew", []):
            if crew.get("job") == "Director":
                director = crew.get("name")
                break
                
    runtime_val = details.get("runtime") or (details.get("episode_run_time")[0] if details.get("episode_run_time") else None)
    runtime = f"{runtime_val} min" if runtime_val else "N/A"
    votes = str(details.get("vote_count", "N/A"))
    
    quality = "1080p WEB-DL"
    if "2160p" in query.lower() or "4k" in query.lower():
        quality = "2160p UHD"
    elif "720p" in query.lower():
        quality = "720p WEB-DL"
        
    languages = "Hindi"
    detected_langs = []
    for lang in ["Hindi", "English", "Punjabi", "Tamil", "Telugu", "Kannada", "Malayalam", "Bengali"]:
        if lang.lower() in query.lower():
            detected_langs.append(lang)
    if detected_langs:
        languages = ", ".join(detected_langs)
        
    ott_platform = "N/A"
    for ott in ["Netflix", "Zee5", "SonyLIV", "JioCinema"]:
        if ott.lower() in query.lower():
            ott_platform = ott
    if "nf" in query.lower():
        ott_platform = "Netflix"
    elif "hotstar" in query.lower() or "hs" in query.lower():
        ott_platform = "Disney+ Hotstar"
    elif "prime" in query.lower() or "amzn" in query.lower():
        ott_platform = "Amazon Prime Video"
        
    return MovieInfo(
        title=title,
        year=year,
        rating=rating,
        genres=genres,
        poster=poster_url,
        plot=plot,
        director=director,
        cast=cast_list,
        runtime=runtime,
        votes=votes,
        languages=languages,
        backdrop=backdrop_url,
        backdrop_url=backdrop_url,
        poster_url=poster_url,
        ott_platform=ott_platform,
        quality=quality,
        type="movie" if media_type == "movie" else "series"
    )

# Async wrapper commonly requested by bots
async def get_movie_detailsx(query, *args, **kwargs):
    return await get_movie_details(query)

# Google Image Search Fallback Scraper to fetch high-res landscape backdrop image
def search_google_landscape_backdrop(movie_title):
    try:
        search_query = f"{movie_title} movie high resolution landscape backdrop wallpaper"
        url = "https://images.google.com/search?q=" + urllib.parse.quote(search_query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=10)
        links = re.findall(r'imgurl=(https?://[^&]+)', r.text)
        if links:
            return urllib.parse.unquote(links[0])
    except Exception as e:
        print(f"Google Image Search Error: {e}")
    return None

# TMDb backdrop search helper
def search_tmdb_backdrop_url(movie_title):
    try:
        api_key = TMDB_API_KEY if TMDB_API_KEY else "c22e0329ff01859b867c2688ca6a5e12"
        search_query = urllib.parse.quote(movie_title)
        url = f"https://api.themoviedb.org/3/search/multi?api_key={api_key}&query={search_query}"
        r = requests.get(url, timeout=10).json()
        if r.get("results"):
            item = r["results"][0]
            backdrop_path = item.get("backdrop_path")
            if backdrop_path:
                return f"https://image.tmdb.org/t/p/original{backdrop_path}"
    except Exception as e:
        print(f"TMDb API Backdrop Error: {e}")
    return None

# Generates clean, stunning cinematic landscape poster with bold red title centered at the bottom
def generate_odyssey_title_poster(movie_title, backdrop_url=None):
    W, H = 1280, 720
    img = None
    
    if backdrop_url:
        try:
            r = requests.get(backdrop_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content))
        except Exception as e:
            print(f"Error downloading backdrop: {e}")

    # Fallback to Google images search if TMDb backdrop was empty or failed
    if img is None:
        google_url = search_google_landscape_backdrop(movie_title)
        if google_url:
            try:
                r = requests.get(google_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content))
            except Exception as e:
                print(f"Error downloading Google backdrop: {e}")

    # Crop and scale background image to fit widescreen 16:9 ratio perfectly
    if img:
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
        # Clean solid modern dark slate-blue gradient fallback if no background image is found
        img = Image.new("RGB", (W, H), color="#090a10")

    draw = ImageDraw.Draw(img, "RGBA")

    # Draw bottom-up vignette gradient (perfect for bottom-centered cinematic titles)
    for y in range(H):
        if y > int(H * 0.35):
            opacity = int(240 * ((y - H * 0.35) / (H * 0.65)))
            draw.rectangle([(0, y), (W, y)], fill=(0, 0, 0, opacity))

    # Clean the title from words like 10BIT and remove any 4-digit year
    clean_title = movie_title.upper().replace("10BIT", "").strip()
    clean_title = re.sub(r'\(?\b(19|20)\d{2}\b\)?', '', clean_title).strip()
    words = clean_title.split()
    
    font = None
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except IOError:
        try:
            font = ImageFont.truetype("LiberationSans-Bold.ttf", 64)
        except IOError:
            font = ImageFont.load_default()

    # Draw wrap-aligned cinematic letters with spacious 20px tracking
    max_text_width = int(W * 0.85)
    spacing = 20
    
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

    font_height = 70
    total_text_height = len(lines) * (font_height * 1.3)
    start_y = H - total_text_height - 55
    
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
            
        total_line_width = sum(char_widths) + (len(chars) - 1) * spacing
        curr_x = (W - total_line_width) // 2  # Perfect horizontal centering
        
        for idx, char in enumerate(chars):
            # 1. Elegant drop shadow for absolute legibility on any backdrop texture
            draw.text((curr_x + 3, start_y + 3), char, fill=(0, 0, 0, 240), font=font)
            # 2. Crisp, beautiful Cinematic RED text fill (#E50914)
            draw.text((curr_x, start_y), char, fill=(229, 9, 20, 255), font=font)
            curr_x += char_widths[idx] + spacing
            
        start_y += int(font_height * 1.3)

    return img

# Posts movie with automatically generated high quality cinematic poster
async def post_movie_with_generated_poster(bot, message, movie_title, backdrop_url=None, caption="", reply_markup=None):
    if not backdrop_url:
        backdrop_url = search_tmdb_backdrop_url(movie_title)
        
    img = generate_odyssey_title_poster(movie_title, backdrop_url)
    
    # Save image to BytesIO memory buffer
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=95)
    img_bytes.seek(0)
    
    # CRITICAL PYROGRAM FIX: Explicitly name the buffer so Pyrogram treats it as a file pointer!
    img_bytes.name = "poster.jpg"

    try:
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=img_bytes,
            caption=caption,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error sending title poster photo: {e}")
        # Message fallback
        await bot.send_message(
            chat_id=message.chat.id,
            text=caption,
            reply_markup=reply_markup
        )
