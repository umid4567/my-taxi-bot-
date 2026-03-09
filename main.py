import os
import asyncio
import requests
from math import radians, cos, sin, asin, sqrt
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
HAYDOVCHI_ID = 7748146680 
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot/"

KM_NARXI = 3500      
MINIMAL_NARX = 6000   

bot = Bot(token=TOKEN)
dp = Dispatcher()

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371 
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2) ** 2
    return round(R * 2 * asin(sqrt(a)), 2)

# --- 1. START ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.from_user.id == HAYDOVCHI_ID:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Lokatsiyamni yangilash", request_location=True)]], resize_keyboard=True)
        await message.answer("Xush kelibsiz! Bot xizmatga tayyor.", reply_markup=kb)
    else:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🚖 Taksi chaqirish", request_location=True)]], resize_keyboard=True)
        await message.answer("Salom! Taksi kerak bo'lsa, pastdagi tugmani bosing 👇", reply_markup=kb)

# --- 2. LOKATSIYA YUBORILGANDA ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat, lon = message.location.latitude, message.location.longitude

    if uid == HAYDOVCHI_ID:
        requests.put(f"{BASE_URL}driver_location.json", json={"lat": lat, "lon": lon})
        await message.answer("✅ Lokatsiyangiz yangilandi.")
    else:
        requests.put(f"{BASE_URL}orders/{uid}.json", json={"lat": lat, "lon": lon, "name": message.from_user.full_name})
        kb_c = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"c_cancel_{uid}")]])
        await message.answer("🚕 Buyurtma haydovchiga yuborildi. Iltimos kuting...", reply_markup=kb_c)

        kb_h = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"ok_{uid}")],
            [InlineKeyboardButton(text="💬 Telegram aloqa", url=f"tg://user?id={uid}")]
        ])
        await bot.send_message(HAYDOVCHI_ID, f"🔔 **YANGI BUYURTMA!**\n👤 {message.from_user.full_name}\n📍 [Xaritada ko'r](https://yandex.uz/maps/?pt={lon},{lat}&z=16&l=map)", reply_markup=kb_h, parse_mode="Markdown")

# --- 3. QABUL QILISH (Haydovchi bosganda) ---
@dp.callback_query(F.data.startswith("ok_"))
async def accept_order(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[1])
    order = requests.get(f"{BASE_URL}orders/{c_id}.json").json()
    if not order:
        await callback.answer("⚠️ Bekor qilingan!")
        return

    nav = f"https://yandex.uz/maps/?rtext=~{order['lat']},{order['lon']}&rtt=auto"
    kb_h = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Navigator", url=nav)],
        [InlineKeyboardButton(text="🚖 TAXI KELDI", callback_data=f"arrived_{c_id}")],
        [InlineKeyboardButton(text="▶️ SAFARNI BOSHLASH", callback_data=f"start_{c_id}")],
        [InlineKeyboardButton(text="💬 Yo'lovchi bilan bog'lanish", url=f"tg://user?id={c_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"d_cancel_{c_id}")]
    ])
    await callback.message.edit_text(f"✅ {order['name']} buyurtmasini qabul qildingiz.", reply_markup=kb_h)

    kb_c = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚖 Haydovchini kuzatish", web_app=WebAppInfo(url=XARITA_LINKI))],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"c_cancel_{c_id}")]
    ])
    await bot.send_message(c_id, "🚕 Haydovchi buyurtmani qabul qildi!", reply_markup=kb_c)
    await callback.answer()

# --- 4. TAXI KELDI ---
@dp.callback_query(F.data.startswith("arrived_"))
async def driver_arrived(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[1])
    await bot.send_message(c_id, "🚕 **Taksi keldi!**\n\nIltimos, tashqariga chiqishingiz mumkin.")
    await callback.answer("Mijozga xabar yuborildi!", show_alert=True)

# --- 5. SAFARNI BOSHLASH ---
@dp.callback_query(F.data.startswith("start_"))
async def start_trip(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[1])
    d_loc = requests.get(f"{BASE_URL}driver_location.json").json()
    if d_loc:
        requests.put(f"{BASE_URL}active_trips/{c_id}.json", json={"s_lat": d_loc['lat'], "s_lon": d_loc['lon']})
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 SAFARNI TUGATISH", callback_data=f"stop_{c_id}")]])
        await callback.message.edit_text("📟 Taksometr yoqildi... Safar yakunida tugmani bosing.", reply_markup=kb)
        await bot.send_message(c_id, "🚖 Safaringiz boshlandi.")
    await callback.answer()

# --- 6. SAFARNI TUGATISH ---
@dp.callback_query(F.data.startswith("stop_"))
async def stop_trip(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[1])
    s_loc = requests.get(f"{BASE_URL}active_trips/{c_id}.json").json()
    d_loc = requests.get(f"{BASE_URL}driver_location.json").json()
    if s_loc and d_loc:
        dist = calculate_distance(s_loc['s_lat'], s_loc['s_lon'], d_loc['lat'], d_loc['lon'])
        narx = max(int(round((dist * KM_NARXI) / 500) * 500), MINIMAL_NARX)
        res = f"🏁 **Safar yakunlandi!**\n📏 Masofa: `{dist}` km\n💰 Jami: **{narx:,}** so'm"
        await callback.message.edit_text(res, parse_mode="Markdown")
        await bot.send_message(c_id, res, parse_mode="Markdown")
        requests.delete(f"{BASE_URL}active_trips/{c_id}.json")
        requests.delete(f"{BASE_URL}orders/{c_id}.json")
    await callback.answer()

# --- 7. BEKOR QILISHLAR ---
@dp.callback_query(F.data.startswith("c_cancel_"))
async def client_cancel(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[2])
    requests.delete(f"{BASE_URL}orders/{c_id}.json")
    await callback.message.edit_text("❌ Buyurtmangiz bekor qilindi.")
    await bot.send_message(HAYDOVCHI_ID, f"🚫 Yo'lovchi (ID: {c_id}) bekor qildi.")
    await callback.answer()

@dp.callback_query(F.data.startswith("d_cancel_"))
async def driver_cancel(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[2])
    await callback.message.edit_text("❌ Siz buyurtmani bekor qildingiz.")
    await bot.send_message(c_id, "😔 Uzr, haydovchi buyurtmani bekor qildi.")
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

