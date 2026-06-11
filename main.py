import logging
import sqlite3
import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# --- SOZLAMALAR (SETTINGS) ---
API_TOKEN = '8833376973:AAGSGaaoC1fpxeAFuBqiSrhjBA8MaDc1qWg'
ADMIN_ID = 8958302600 

# @ELBEKSOFTUZ kanalingiz ID raqami
CHANNEL_ID = -1003966562310  

# MemoryStorage - Holatlarni eslab qolish uchun
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
logging.basicConfig(level=logging.INFO)

# --- BAZANI SOZLANISHI (DATABASE SETUP) ---
conn = sqlite3.connect("elbeksoft.db", check_same_thread=False)
cursor = conn.cursor() 

try:
    cursor.execute("DROP TABLE IF EXISTS files")
    cursor.execute("DROP TABLE IF EXISTS users")
    conn.commit()
    logging.info("🗑️ Eski ma'lumotlar bazasi muvaffaqiyatli tozalandi!")
except Exception as e:
    logging.error(f"Bazani tozalashda xato: {e}")

cursor.execute('''CREATE TABLE IF NOT EXISTS files 
                  (id INTEGER PRIMARY KEY,
                   file_id TEXT UNIQUE,
                   file_type TEXT,
                   category TEXT,
                   game_name TEXT,
                   caption TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, username TEXT, fullname TEXT)''')
conn.commit()

class FeedbackState(StatesGroup):
    waiting_for_message = State()

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💻 Windows", "⚙️ Drivers", "📦 Soft", "🎮 Games", "📥 Torrent")
    markup.add("✍️ Contact Admin")
    return markup

def get_file_markup(cat, offset, total):
    markup = InlineKeyboardMarkup()
    if offset > 0:
        markup.insert(InlineKeyboardButton("⬅️", callback_data=f"page_{cat}_{offset-5}"))
    if offset + 5 < total:
        markup.insert(InlineKeyboardButton("➡️", callback_data=f"page_{cat}_{offset+5}"))
    return markup

def get_game_markup(game_name, offset, total):
    markup = InlineKeyboardMarkup()
    if offset > 0:
        markup.insert(InlineKeyboardButton("⬅️", callback_data=f"gpage|{game_name}|{offset-5}"))
    if offset + 5 < total:
        markup.insert(InlineKeyboardButton("➡️", callback_data=f"gpage|{game_name}|{offset+5}"))
    return markup

@dp.channel_post_handler(content_types=['document', 'video', 'photo'])
async def auto_save(message: types.Message):
    if message.chat.id != CHANNEL_ID: 
        return
    
    caption = (message.caption or "").lower()
    tags = [word.replace('#', '') for word in caption.split() if word.startswith('#')]
    
    cat_map = {
        "windows": "Windows", 
        "drivers": "Drivers", "drayverlar": "Drivers",
        "soft": "Soft", 
        "games": "Games", "o'yinlar": "Games",
        "torrent": "Torrent"
    }
    
    category = "Other"
    for tag in tags:
        if tag in cat_map:
            category = cat_map[tag]
            break
            
    game_name = "other"
    if category == "Games":
        game_name = next((tag for tag in tags if tag not in ["games", "o'yinlar"]), "other")

    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    else:
        return
    
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO files
            (file_id, file_type, category, game_name, caption)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_id, file_type, category, game_name, caption)
        )
        conn.commit()
        logging.info(f"✅ Fayl muvaffaqiyatli saqlandi! Kategoriya: {category}")
    except Exception as e: 
        logging.error(f"Baza xatoligi: {e}")

@dp.message_handler(lambda m: m.text == "✍️ Contact Admin")
async def contact_admin_start(message: types.Message):
    await message.answer("📝 Iltimos, adminstratorga yubormoqchi bo'lgan xabaringizni yozing:",
                         reply_markup=types.ReplyKeyboardRemove())
    await FeedbackState.waiting_for_message.set()

@dp.message_handler(state=FeedbackState.waiting_for_message, content_types=types.ContentTypes.ANY)
async def forward_to_admin(message: types.Message, state: FSMContext):
    await state.finish()
    
    user_info = f"📩 Yangi xabar!\n\nKimdan: {message.from_user.full_name}\nID: {message.from_user.id}\nUsername: @{message.from_user.username or 'Mavjud_emas'}\n\nXabar:\n"
    
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=user_info)
        await message.forward(chat_id=ADMIN_ID)
        await message.answer("✅ Xabaringiz adminga yetkazildi! Tez orada javob qaytaramiz.", reply_markup=get_main_menu())
    except Exception as e:
        await message.answer("❌ Xabarni yuborishda xatolik yuz berdi.", reply_markup=get_main_menu())

@dp.message_handler(lambda m: m.reply_to_message and m.chat.id == ADMIN_ID, content_types=types.ContentTypes.ANY)
async def admin_reply_handler(message: types.Message):
    try:
        if message.reply_to_message.forward_from:
            target_user_id = message.reply_to_message.forward_from.id
        else:
            text = message.reply_to_message.text or ""
            lines = text.split("\n")
            target_user_id = None
            for line in lines:
                if line.startswith("ID: "):
                    target_user_id = int(line.replace("ID: ", "").strip())
                    break
        if target_user_id:
            if message.text:
                await bot.send_message(target_user_id, f"💬 Admin javobi:\n\n{message.text}")
            else:
                await message.copy_to(target_user_id)
            await message.reply("✅ Javobingiz foydalanuvchiga yuborildi!")
        else:
            await message.reply("❌ Foydalanuvchi ID raqamini aniqlab bo'lmadi.")
    except Exception as e:
        await message.reply(f"❌ Xabar yuborilmadi: {e}")

@dp.message_handler(lambda m: m.text == "🎮 Games")
async def games_menu(message: types.Message):
    cursor.execute("SELECT DISTINCT game_name FROM files WHERE category = ? AND game_name != ?", ("Games", "other"))
    games = cursor.fetchall()
    
    if not games:
        await message.answer("🎮 O'yinlar bo'limi hozircha bo'sh.\n\nKanalga faylni #games #o_yin_nomi heshteglari bilan yuklang!")
        return
        
    markup = InlineKeyboardMarkup(row_width=2)
    for game in games:
        markup.insert(InlineKeyboardButton(game[0].upper().replace('_', ' '), callback_data=f"game|{game[0]}|0"))
    await message.answer("🎮 Kerakli o'yinni tanlang:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("game|") or c.data.startswith("gpage|"))
async def show_game_parts(call: types.CallbackQuery):
    _, game_name, offset = call.data.split('|')
    offset = int(offset)
    
    cursor.execute("SELECT file_id, file_type, caption FROM files WHERE game_name = ? ORDER BY id DESC LIMIT 5 OFFSET ?", (game_name, offset))
    results = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM files WHERE game_name = ?", (game_name,))
    total = cursor.fetchone()[0]
    
    if not results:
        await call.answer("❌ Fayllar topilmadi.", show_alert=True)
        return
        
    text = f"📁 {game_name.upper().replace('_', ' ')} (Jami: {total} qism, Sahifa: {offset//5 + 1})"
    
    try:
        await call.message.edit_text(text, reply_markup=get_game_markup(game_name, offset, total))
    except Exception as e:
        logging.error(e)
        
    chat_id = call.message.chat.id
    for file in results:
        try:
            file_id = file[0]
            file_type = file[1]
            caption = (file[2] or "")[:100]

            if file_type == "document":
                await bot.send_document(chat_id=chat_id, document=file_id, caption=caption)
            elif file_type == "video":
                await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
            elif file_type == "photo":
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
        except Exception as e:
            continue

async def show_category_page(msg_or_call, cat, offset):
    cursor.execute("SELECT file_id, file_type, caption FROM files WHERE category = ? ORDER BY id DESC LIMIT 5 OFFSET ?", (cat, offset))
    results = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM files WHERE category = ?", (cat,))
    total = cursor.fetchone()[0]

    if isinstance(msg_or_call, types.Message):
        chat_id = msg_or_call.chat.id
    else:
        chat_id = msg_or_call.message.chat.id

    if not results:
        if isinstance(msg_or_call, types.Message):
            await msg_or_call.answer("❌ Bu bo'limda hozircha fayllar yo'q.")
        else:
            await msg_or_call.answer("❌ Boshqa fayl topilmadi.", show_alert=True)
        return

    text = f"📁 {cat} Bo'limi (Jami: {total} fayl, Sahifa: {offset//5 + 1})"
    
    if isinstance(msg_or_call, types.Message):
        await msg_or_call.answer(text, reply_markup=get_file_markup(cat, offset, total))
    else:
        try:
            await msg_or_call.message.edit_text(text, reply_markup=get_file_markup(cat, offset, total))
        except Exception as e:
            logging.error(e)
    
    for file in results:
        try:
            file_id = file[0]
            file_type = file[1]
            caption = (file[2] or "")[:100]

            if file_type == "document":
                await bot.send_document(chat_id=chat_id, document=file_id, caption=caption)
            elif file_type == "video":
                await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
            elif file_type == "photo":
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
        except Exception as e:
            continue

@dp.message_handler(lambda m: m.text in ["💻 Windows", "⚙️ Drivers", "📦 Soft", "📥 Torrent"])
async def category_handler(message: types.Message):
    mapping = {"💻 Windows": "Windows", "⚙️ Drivers": "Drivers", "📦 Soft": "Soft", "📥 Torrent": "Torrent"}
    cat = mapping.get(message.text)
    await show_category_page(message, cat, 0)

@dp.callback_query_handler(lambda c: c.data.startswith('page_'))
async def pagination_handler(call: types.CallbackQuery):
    _, cat, offset = call.data.split('_')
    await show_category_page(call, cat, int(offset))

@dp.message_handler(commands=['admin', 'stats'], user_id=ADMIN_ID)
async def admin_panel(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM files")
    total_files = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    admin_text = (
        "⚙️ **ADMIN PANELIGA XUSH KELIBSIZ** ⚙️\n\n"
        f"📊 **Jami ro'yxatdan o'tganlar:** {total_users}\n"
        f"📁 **Bazadagi jami fayllar:** {total_files}\n\n"
        "💡 *Foydalanuvchiga javob berish uchun uning kelgan xabariga shunchaki 'Reply' qiling.*"
    )
    await message.answer(admin_text, parse_mode="Markdown")

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, fullname) VALUES (?, ?, ?)",
                       (message.from_user.id, message.from_user.username, message.from_user.full_name))
        conn.commit()
    except Exception as e:
        logging.error(f"Foydalanuvchini saqlashda xato: {e}")

    await message.answer("Xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=get_main_menu())

# --- RENDER PORTINI KUTISH QISMI (SOZLANISHI) ---
async def on_startup(dp):
    # Render so'raydigan dummy port yaratadi
    port = int(os.environ.get("PORT", 10000))
    server = await asyncio.start_server(lambda r, w: None, '0.0.0.0', port)
    logging.info(f"🟢 Render porti eshitilyapti: {port}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
