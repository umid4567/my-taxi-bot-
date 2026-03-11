import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
# GitHubdagi xarita manzilingiz
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot/" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 1. START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()

    if user_data and user_data.get("role") == "driver":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Yangi buyurtmalarni kutish")],
            [KeyboardButton(text="💰 Mening balansim")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, haydovchi {user_data.get('name')}!", reply_markup=kb)

    elif user_data and user_data.get("role") == "client":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚕 Taksi chaqirish", request_location=True)],
            [KeyboardButton(text="ℹ️ Ma'lumot")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer("Xush kelibsiz! Taksi kerak bo'lsa tugmani bosing.", reply_markup=kb)
    
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Rolingizni tanlang:", reply_markup=kb_start)

# --- 2. ROLNI O'CHIRISH ---
@dp.message(F.text == "🔄 Rolni o'zgartirish")
@dp.message(Command("reset"))
async def reset_user(message: Message):
    uid = message.from_user.id
    requests.delete(f"{BASE_URL}users/{uid}.json")
    await message.answer("🔄 Ma'lumotlaringiz o'chirildi.\n/start bosing.", reply_markup=types.ReplyKeyboardRemove())

# --- 3. ROLNI SAQLASH ---
@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    uid = callback.from_user.id
    requests.put(f"{BASE_URL}users/{uid}.json", json={"role": role, "name": callback.from_user.full_name})
    await callback.message.answer(f"✅ Saqlandi! /start bosing.")
    await callback.answer()

# --- 4. BUYURTMA BERISH ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude
    
    # 1. Buyurtmani bazaga saqlaymiz
    requests.put(f"{BASE_URL}orders/{uid}.json", json={
        "lat": lat, 
        "lon": lon, 
        "name": message.from_user.full_name
    })
    
    await message.answer("🚕 Buyurtmangiz haydovchilarga yuborildi. Iltimos kuting...")
    
    # 2. Hamma haydovchilarga xabar yuboramiz
    all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    for d_id, data in all_users.items():
        if data.get("role") == "driver":
            # DIQQAT: Mana shu yerda lat va lon-ni callback_data ichiga qo'shish shart!
            kb_h = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Qabul qilish", 
                    callback_data=f"accept_{uid}_{lat}_{lon}" # SHU YERDA XATO BO'LSA MARSHRUT CHIZILMAYDI
                )]
            ])
            
            await bot.send_message(
                d_id, 
                f"🔔 **Yangi buyurtma!**\n👤 Yo'lovchi: {message.from_user.full_name}", 
                reply_markup=kb_h
            )


# --- 5. QABUL QILISH (WEB APP MARSHRUT BILAN) ---
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    data = callback.data.split("_")
    c_id = data[1]
    c_lat = data[2]
    c_lon = data[3]
    
    requests.delete(f"{BASE_URL}orders/{c_id}.json")
    
    # Marshrut linki: haydovchi xaritani ochganda mijoz koordinatalarini olib ketadi
    marshrut_link = f"{XARITA_LINKI}?clat={c_lat}&clon={c_lon}"
    
    kb_app = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Marshrutni ko'rish (Botda)", web_app=WebAppInfo(url=marshrut_link))]
    ])
    
    await callback.message.edit_text("✅ Buyurtma qabul qilindi!", reply_markup=kb_app)
    await bot.send_message(c_id, "🚕 Haydovchi yo'lga chiqdi!")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
