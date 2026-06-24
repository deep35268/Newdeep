import re
import os
from os import environ, getenv
from Script import script

# Utility functions
id_pattern = re.compile(r'^.\d+$')

def is_enabled(value, default):
    if isinstance(value, bool):
        return value
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# ============================
# Bot Information Configuration
# ============================
SESSION = environ.get('SESSION', 'dreamxbotz_search')   
API_ID = int(environ.get('API_ID', '25625749')) 
API_HASH = environ.get('API_HASH', '1b4a47426f1189e4c406057be9735e3b')  
BOT_TOKEN = environ.get('BOT_TOKEN', "")    

# ============================
# Bot Settings Configuration
# ============================
CACHE_TIME = int(environ.get('CACHE_TIME', 300))    
USE_CAPTION_FILTER = is_enabled(environ.get('USE_CAPTION_FILTER', "True"), True)  
INDEX_CAPTION = is_enabled(environ.get('SAVE_CAPTION', "True"), True) 
COVERX = is_enabled(environ.get('COVERX', "True"), True) 

PICS_URL = (environ.get('PICS', 'https://graph.org/file/e5eebc6d5caa2f7ced006-9c13a283682117858c.jpg')).split() 
PICS = (environ.get('PICS', 'https://graph.org/file/e5eebc6d5caa2f7ced006-9c13a283682117858c.jpg')).split()  
NOR_IMG = environ.get("NOR_IMG", "https://graph.org/file/e20b5fdaf217252964202.jpg")
MELCOW_PHOTO = environ.get("MELCOW_PHOTO", "https://i.imgur.com/vt2AfIN.jpeg")
SPELL_IMG = environ.get("SPELL_IMG", "https://graph.org/file/13702ae26fb05df52667c.jpg")
SUBSCRIPTION = (environ.get('SUBSCRIPTION', 'https://graph.org/file/242b7f1b52743938d81f1.jpg'))
FSUB_PICS = (environ.get('FSUB_PICS', 'https://graph.org/file/7478ff3eac37f4329c3d8.jpg https://graph.org/file/56b5deb73f3b132e2bb73.jpg')).split()  

# ============================
# Admin, Channels & Users Configuration
# ============================
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '6467566398').split()] 
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', '-1003954712996').split()]  

LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-1002427494480'))  
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', '-1002160542554'))  
PREMIUM_LOGS = int(environ.get('PREMIUM_LOGS', '-1001970548842'))  
DELETE_CHANNELS = [int(dch) if id_pattern.search(dch) else dch for dch in environ.get('DELETE_CHANNELS', '-1002479259622').split()] 
support_chat_id = environ.get('SUPPORT_CHAT_ID', '-1002216002151')  
reqst_channel = environ.get('REQST_CHANNEL_ID', '-1002290453638')  
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', 'https://t.me/Ownersupport')  

# FORCE_SUB 
auth_req_channels = environ.get("AUTH_REQ_CHANNELS", "-100")  
auth_channels     = environ.get("AUTH_CHANNELS", "-1002151783803")

# ============================
# Payment Configuration
# ============================
QR_CODE = environ.get('QR_CODE', 'https://iili.io/KQ4BhIS.md.jpg')    
OWNER_UPI_ID = environ.get('OWNER_UPI_ID', 'deep2213n@ptyes')    

STAR_PREMIUM_PLANS = {
    10: "7day",
    20: "15day",    
    40: "1month", 
    55: "45day",
    75: "60day",
}  

# ============================
# MongoDB Configuration
# ============================
DATABASE_URI = environ.get('DATABASE_URI', "mongodb+srv://jagdeep2213:6cWXzIwCi4Cz8ynp@cluster0.ewdwnyq.mongodb.net/?retryWrites=true&w=majority")  
DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0") 
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'dreamcinezone_files') 

MULTIPLE_DB = is_enabled(os.environ.get('MULTIPLE_DB', "False"), False) 
DATABASE_URI2 = environ.get('DATABASE_URI2', "mongodb+srv://hhhkkkbbb:devils21@cluster0.xuqky.mongodb.net/?retryWrites=true&w=majority")  

# ==========================================
# ⚡ MOVIE NOTIFICATION & UPDATE SETTINGS
# ==========================================
MOVIE_UPDATE_NOTIFICATION = is_enabled(environ.get('MOVIE_UPDATE_NOTIFICATION', "True"), True)  
MOVIE_UPDATE_CHANNEL = int(environ.get('MOVIE_UPDATE_CHANNEL', '-1003752618894'))  
DREAMXBOTZ_IMAGE_FETCH = is_enabled(environ.get('DREAMXBOTZ_IMAGE_FETCH', "True"), True)  
LINK_PREVIEW = is_enabled(environ.get('LINK_PREVIEW', "False"), False) 
ABOVE_PREVIEW = is_enabled(environ.get('ABOVE_PREVIEW', "True"), True) 

# 🔐 ਨਵੀਂ ਵਰਕਿੰਗ API Key (ਪੁਰਾਣੀ ਬਲਾਕ ਹੋਣ ਕਰਕੇ 401 ਐਰਰ ਦੇ ਰਹੀ ਸੀ)
TMDB_API_KEY = environ.get('TMDB_API_KEY', 'e105e192ff816027b4092b7c46f3d9e8') 
TMDB_POSTER = True 
LANDSCAPE_POSTER = True 

# ============================
# Verification Settings
# ============================
IS_VERIFY = is_enabled(environ.get('IS_VERIFY', "False"), False)  
LOG_VR_CHANNEL = int(environ.get('LOG_VR_CHANNEL', '-1002160542554')) 
LOG_API_CHANNEL = int(environ.get('LOG_API_CHANNEL', '-1002160542554')) 
VERIFY_IMG = environ.get("VERIFY_IMG", "https://telegra.ph/file/9ecc5d6e4df5b83424896.jpg")

TUTORIAL = environ.get("TUTORIAL", "https://t.me/HOWTO61")   
TUTORIAL_2 = environ.get("TUTORIAL_2", "https://t.me/HOWTO61")   
TUTORIAL_3 = environ.get("TUTORIAL_3", "https://t.me/HOWTO6")   

SHORTENER_API = environ.get("SHORTENER_API", "a7ac9b3012c67d7491414cf272d82593c75f6cbb") 
SHORTENER_WEBSITE = environ.get("SHORTENER_WEBSITE", "omegalinks.in") 

SHORTENER_API2 = environ.get("SHORTENER_API2", "7709a824575640328a543091da04875a63be6d95")  
SHORTENER_WEBSITE2 = environ.get("SHORTENER_WEBSITE2", "shortxlinks.com") 

SHORTENER_API3 = environ.get("SHORTENER_API3", "7709a824575640328a543091da04875a63be6d95")  
SHORTENER_WEBSITE3 = environ.get("SHORTENER_WEBSITE3", "shortxlinks.com") 

TWO_VERIFY_GAP = int(environ.get('TWO_VERIFY_GAP', "86400")) 
THREE_VERIFY_GAP = int(environ.get('THREE_VERIFY_GAP', "54000"))    

# ============================
# Channel & Group Links Configuration
# ============================
GRP_LNK = environ.get('GRP_LNK', 'https://t.me/Moviesrequst01') 
OWNER_LNK = environ.get('OWNER_LNK', 'https://t.me/Deep2213k') 
UPDATE_CHNL_LNK = environ.get('UPDATE_CHNL_LNK', 'https://t.me/+_G-JQx6Ll2RjNTU1') 

# ============================
# User Configuration
# ============================
auth_users = [int(user) if id_pattern.search(user) else user for user in environ.get('AUTH_USERS', '').split()]
AUTH_USERS = (auth_users + ADMINS) if auth_users else []
PREMIUM_USER = [int(user) if id_pattern.search(user) else user for user in environ.get('PREMIUM_USER', '').split()]

# ============================
# Miscellaneous Configuration
# ============================
ULTRA_FAST_MODE = is_enabled(environ.get('ULTRA_FAST_MODE', "False"), True) 

MAX_B_TN = environ.get("MAX_B_TN", "5") 
PORT = int(environ.get("PORT", "8080"))  
MSG_ALRT = environ.get('MSG_ALRT', 'Share & Support Us ♥️') 
DELETE_TIME = int(environ.get("DELETE_TIME", "300"))  
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")   
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION) 

# 🎬 ਤੁਹਾਡਾ ਮਨਪਸੰਦ ਫਾਰਮੈਟ 
IMDB_TEMPLATE = """🎬 <code>{title}{year}</code>

⭐ IMDb: {rating}/10

📌 (Touch To Copy)

➡ Audio Track:- 🔊 {languages}

Added ✅"""

MAX_LIST_ELM = int(environ.get("MAX_LIST_ELM") or 10) or None 
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))  
NO_RESULTS_MSG = is_enabled(environ.get("NO_RESULTS_MSG", "True"), True)  
MAX_BTN = is_enabled((environ.get('MAX_BTN', "True")), True)    
P_TTI_SHOW_OFF = is_enabled((environ.get('P_TTI_SHOW_OFF', "False")), False)    

IMDB = is_enabled((environ.get('IMDB', "True")), True)    
TMDB_ON_SEARCH = is_enabled((environ.get('TMDB_ON_SEARCH', "True")), True)    

AUTO_FFILTER = is_enabled((environ.get('AUTO_FFILTER', "True")), True) 
AUTO_DELETE = is_enabled((environ.get('AUTO_DELETE', "True")), True) 
LONG_IMDB_DESCRIPTION = is_enabled(environ.get("LONG_IMDB_DESCRIPTION", "False"), False) 
SPELL_CHECK_REPLY = is_enabled(environ.get("SPELL_CHECK_REPLY", "True"), True) 
MELCOW_NEW_USERS = is_enabled((environ.get('MELCOW_NEW_USERS', "False")), False) 
PROTECT_CONTENT = is_enabled((environ.get('PROTECT_CONTENT', "False")), False) 
PM_SEARCH = is_enabled(environ.get('PM_SEARCH', "True"), True)  
EMOJI_MODE = is_enabled(environ.get('EMOJI_MODE', "True"), True)  
BUTTON_MODE = is_enabled((environ.get('BUTTON_MODE', "False")), False) 
STREAM_MODE = is_enabled(environ.get('STREAM_MODE', "True"), True) 
PREMIUM_STREAM_MODE = is_enabled(environ.get('PREMIUM_STREAM_MODE', "False"), False) 
MAINTENANCE = is_enabled(environ.get('MAINTENANCE', "False"), False)

AUTH_REQ_CHANNELS = [int(ch) for ch in auth_req_channels.split() if ch and id_pattern.match(ch)] 
AUTH_CHANNELS = [int(ch) for ch in auth_channels.split() if ch and id_pattern.match(ch)]
REQST_CHANNEL = int(reqst_channel) if reqst_channel and id_pattern.search(reqst_channel) else None
SUPPORT_CHAT_ID = int(support_chat_id) if support_chat_id and id_pattern.search(support_chat_id) else None
LANGUAGES = {"ᴍᴀʟᴀʏᴀʟᴀᴍ":"mal","ᴛᴀᴍɪʟ":"tam","ᴇɴɢʟɪsʜ":"eng","ʜɪɴᴅɪ":"hin","ᴛᴇʟᴜɢᴜ":"tel","ᴋᴀɴɴᴀᴅᴀ":"kan","ɢᴜᴊᴀʀᴀᴛɪ":"guj","ᴍᴀʀᴀᴛʜɪ":"mar","ᴘᴜɴᴊᴀʙɪ":"pun"}
QUALITIES = ["360P", "480P", "720P", "1080P", "1440P", "2160P", "4K"]

SEASON_COUNT = 12
SEASONS = [f"S{str(i).zfill(2)}" for i in range(1, SEASON_COUNT + 1)]

BAD_WORDS = {"PrivateMovieZ", "toonworld4all", "themoviesboss", "1tamilmv", "tamilblasters", "1tamilblasters", "skymovieshd", "extraflix", "hdm2", "moviesmod", "hdhub4u", "mkvcinemas", "primefix", "join", "www", "villa", "tg", "original"}

NO_PORT = is_enabled(environ.get('NO_PORT', "False"), False)
APP_NAME = None
if 'DYNO' in environ:
    ON_HEROKU = True
    APP_NAME = environ.get('APP_NAME')
else:
    ON_HEROKU = False
BIND_ADRESS = str(getenv('WEB_SERVER_BIND_ADDRESS', '0.0.0.0'))
FQDN = str(getenv('FQDN', BIND_ADRESS)) if not ON_HEROKU or getenv('FQDN') else f"{APP_NAME}.herokuapp.com"
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '60'))
WORKERS = int(environ.get('WORKERS', '4'))
SESSION_NAME = str(environ.get('SESSION_NAME', 'dreamXBotz'))
MULTI_CLIENT = False
name = str(environ.get('name', 'DREAMXBOTZ'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "1200"))  

HAS_SSL = is_enabled(getenv('HAS_SSL', "True"), True)

if HAS_SSL:
    URL = f"https://{FQDN}/" if not FQDN.startswith("http") else FQDN
else:
    URL = f"http://{FQDN}/" if not FQDN.startswith("http") else FQDN

REACTIONS = ["🤝", "😇", "🤗", "😍", "👍", "🎅", "😐", "🥰", "🤩", "😱", "🤣", "😘", "👏", "😛", "😈", "🎉", "⚡️", "🫡", "🤓", "😎", "🏆", "🔥", "🤭", "🌚", "🆒", "👻", "😁"]

Bot_cmds = {
    "start": "Sᴛᴀʀᴛ Mᴇ Bᴀʙʏ", "stats": "Gᴇᴛ Bᴏᴛ Sᴛᴀᴛs", "alive": " Cʜੇᴄᴋ Bᴏᴛ Aʟɪᴠੇ ᴏʀ Nᴏᴛ ", "settings": "ᴄʜᴀɴɢੇ sੇᴛᴛɪɴɢs", "id": "ɢੇᴛ ɪᴅ ᴛੇʟੇɢʀᴀᴍ ", "info": "Gੇᴛ Usੇʀ ɪɴғۆ ", "del_msg": "<b>ʀੇᴍᴏᴠੇ ғɪʟੇ ɴᴀᴍੇ...</b>", "movie_update": "ᴏɴ ᴏғғ...", "pm_search": "ᴘᴍ sੇᴀʀᴄʜ...", "trendlist": "Gᴇᴛ Tᴏᴘ Tʀᴀɴᴅɪɴ釋 Sੇᴀʀᴄʜ Lɪsᴛ", "broadcast": "ʙʀᴏᴀᴅᴄᴀсьᴛ...", "grp_broadcast": "ʙʀᴏᴀᴅᴄᴀsᴛ ᴛո ɢʀᴏᴜᴘs", "send": "ꜱੇɴᴅ ᴍੇꜱꜱᴀ章ੇ...", "add_premium": "ᴀᴅᴅ ᴘʀੇᴍɪᴜᴍ", "remove_premium": "<b>ʀੇᴍᴏᴠੇ ᴘʀੇᴍɪᴜᴍ</b>", "premium_users": "ʟɪꜱᴛ...", "restart": "ʀੇꜱᴛᴀʀᴛ...", "group_cmd": "ɢʀᴏᴜᴘ ᴄᴍᴅ", "admin_cmd": "ᴀᴅμɪɴ ᴄμᴅ", "reset_group": "Reset Group", "trial_reset": "Trial Reset", "remove_fsub": "Remove Fsub", "maintenance": "Maintenance Mode"
}

if MULTIPLE_DB == False:
    DATABASE_URI = DATABASE_URI
    DATABASE_URI2 = DATABASE_URI
else:
    DATABASE_URI = DATABASE_URI
    DATABASE_URI2 = DATABASE_URI2

LOG_STR = "Current Customized Configurations are:-\n"
