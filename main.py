import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"

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
            [KeyboardButton(text="💰 Mening balansim")]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, haydovchi {user_data.get('name')}!", reply_markup=kb)

    elif user_data and user_data.get("role") == "client":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚕 Taksi chaqirish", request_location=True)],
            [KeyboardButton(text="ℹ️ Ma'lumot")]
        ], resize_keyboard=True)
        await message.answer("Xush kelibsiz! Taksi kerak bo'lsa tugmani bosing.", reply_markup=kb)
    
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Rolingizni tanlang:", reply_markup=kb_start)

# --- 2. ROLNI SAQLASH ---
@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    uid = callback.from_user.id
    requests.put(f"{BASE_URL}users/{uid}.json", json={"role": role, "name": callback.from_user.full_name})
    await callback.message.answer(f"✅ Tayyor! Endi botni ishlatish uchun qaytadan /start bosing.")
    await callback.answer()

# --- 3. BUYURTMA BERISH ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat, lon = message.location.latitude, message.location.longitude
    
    # Buyurtmani bazaga yozish
    requests.put(f"{BASE_URL}orders/{uid}.json", json={"lat": lat, "lon": lon, "name": message.from_user.full_name})
    await message.answer("🚕 Buyurtmangiz haydovchilarga yuborildi. Iltimos kuting...")
    
    # Haydovchilarga xabar yuborish
    all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    for d_id, data in all_users.items():
        if data.get("role") == "driver":
            kb_h = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{uid}")]
            ])
            map_url = f"https://yandex.uz/maps/?pt={lon},{lat}&z=16&l=map"
            await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤 {message.from_user.full_name}\n📍 [Xaritada ko'rish]({map_url})", reply_markup=kb_h, parse_mode="Markdown")

# --- 4. QABUL QILISH ---
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    requests.delete(f"{BASE_URL}orders/{c_id}.json")
    
    await callback.message.edit_text("✅ Buyurtmani qabul qildingiz!")
    await bot.send_message(c_id, "🚕 Haydovchi buyurtmani qabul qildi va siz tomon yo'lga chiqdi!")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
