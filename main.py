import os
import asyncio
import requests
from math import radians, cos, sin, asin, sqrt
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    WebAppInfo,
    CallbackQuery
)
import requests


# --- VEB SERVER QISMI (CRON-JOB UCHUN) ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "OK"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# ---------------------------------------

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
ADMIN_ID = 7748146680  # Faqat siz /stat ko'ra olasiz
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot/"

KM_NARXI = 4000      
MINIMAL_NARX = 6000  # Minimal narxni 6000 qildim

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
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()

    # HAYDOVCHI UCHUN MENYU
    if user_data and user_data.get("role") == "driver":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚀 Ishni boshlash (Avtomat)", web_app=WebAppInfo(url=XARITA_LINKI))],
            [KeyboardButton(text="💰 Mening balansim")],
            [KeyboardButton(text="📍 Qo'lda yangilash", request_location=True)]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, {user_data.get('name')}! Ishga tayyormisiz?", reply_markup=kb)

    @dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    uid = callback.from_user.id
    name = callback.from_user.full_name

    # Bazaga saqlaymiz (Firebase)
    requests.put(f"{BASE_URL}users/{uid}.json", json={"role": role, "name": name})
    
    await callback.answer("Tanlov saqlandi!")
    await callback.message.answer(f"Tabriklaymiz! Endi siz {role} rolidamisiz. Botni qayta ishga tushirish uchun /start bosing.")

    
    # MIJOZ (YO'LOVCHI) UCHUN MENYU
    elif user_data and user_data.get("role") == "client":
        kb_client = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Taksi chaqirish", request_location=True)], # Lokatsiya so'rash bilan birga
            [KeyboardButton(text="ℹ️ Ma'lumot")]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, {user_data.get('name')}! Qayerga boramiz?", reply_markup=kb_client)
    
    # RO'YXATDAN O'TMAGANLAR UCHUN (BIRINCHI MARTA KIRGANLAR)
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Botdan foydalanish uchun rolingizni tanlang:", reply_markup=kb_start)


# --- 2. LOKATSIYA VA BUYURTMA ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat, lon = message.location.latitude, message.location.longitude
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()

    if user_data and user_data.get("role") == "driver":
        requests.put(f"{BASE_URL}driver_location/{uid}.json", json={"lat": lat, "lon": lon})
        await message.answer("✅ Lokatsiyangiz yangilandi.")
    else:
        # MIJOZ BUYURTMA BERGANDA
        requests.put(f"{BASE_URL}orders/{uid}.json", json={"lat": lat, "lon": lon, "name": message.from_user.full_name})
        await message.answer("🚕 Buyurtma haydovchilarga yuborildi. Iltimos kuting...")
        
        # Barcha faol haydovchilarga yuborish
        all_users = requests.get(f"{BASE_URL}users.json").json() or {}
        for d_id, data in all_users.items():
            if data.get("role") == "driver":
                kb_h = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{uid}")],
                    [InlineKeyboardButton(text="💬 Mijoz bilan bog'lanish", url=f"tg://user?id={uid}")]
                ])
                await bot.send_message(d_id, f"🔔 **YANGI BUYURTMA!**\n👤 {message.from_user.full_name}\n📍 [Xaritada ko'r](https://yandex.uz/maps/?pt={lon},{lat}&z=16&l=map)", reply_markup=kb_h, parse_mode="Markdown")

# --- 3. ROL TANLASH ---
@dp.callback_query(F.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[1]
    uid = callback.from_user.id
    requests.put(f"{BASE_URL}users/{uid}.json", json={"role": role, "name": callback.from_user.full_name})
    await callback.message.edit_text(f"✅ Siz {role} sifatida ro'yxatdan o'tdingiz. /start bosing.")

# --- 4. BUYURTMANI QABUL QILISH (LOCK TIZIMI BILAN) ---
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[1])
    d_id = callback.from_user.id
    
    # Tekshiruv: buyurtma hali bo'shmi?
    order = requests.get(f"{BASE_URL}orders/{c_id}.json").json()
    if not order:
        await callback.answer("❌ Kechikdingiz! Buyurtma olib bo'lingan.", show_alert=True)
        await callback.message.delete()
        return

    # Band qilish
    requests.put(f"{BASE_URL}active_trips/{c_id}.json", json={"s_lat": order['lat'], "s_lon": order['lon'], "d_id": d_id})
    requests.delete(f"{BASE_URL}orders/{c_id}.json")

    nav = f"https://yandex.uz/maps/?rtext=~{order['lat']},{order['lon']}&rtt=auto"
    kb_h = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Navigator", url=nav)],
        [InlineKeyboardButton(text="▶️ SAFARNI BOSHLASH", callback_data=f"start_trip_{c_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"d_cancel_{c_id}")]
    ])
        # 1. Mijoz uchun xarita linki
    MIJOZ_XARITASI = "https://umid4567.github.io/my-taxi-bot/client.html"

    # 2. Mijozga boradigan "Kuzatish" tugmasi
    kb_mijoz = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚖 Haydovchini kuzatish", web_app=WebAppInfo(url=MIJOZ_XARITASI))]
    ])

    # 3. Haydovchi va Mijozga xabarlar
    await callback.message.edit_text(f"✅ Buyurtma qabul qilindi!", reply_markup=kb_h)
    await bot.send_message(c_id, "🚕 Haydovchi qabul qildi va yo'lga chiqdi!", reply_markup=kb_mijoz)


# --- 5. SAFARNI BOSHLASH VA TUGATISH ---
@dp.callback_query(F.data.startswith("start_trip_"))
async def start_trip_btn(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 SAFARNI TUGATISH", callback_data=f"stop_{c_id}")]])
    await callback.message.edit_text("📟 Taksometr ishlamoqda...", reply_markup=kb)
    await bot.send_message(c_id, "🚖 Safaringiz boshlandi.")

@dp.callback_query(F.data.startswith("stop_"))
async def stop_trip(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[1])
    d_id = callback.from_user.id
    
    s_loc = requests.get(f"{BASE_URL}active_trips/{c_id}.json").json()
    d_loc = requests.get(f"{BASE_URL}driver_location/{d_id}.json").json()
    
    if s_loc and d_loc:
        dist = calculate_distance(s_loc['s_lat'], s_loc['s_lon'], d_loc['lat'], d_loc['lon'])
        narx = max(int(round((dist * KM_NARXI) / 500) * 500), MINIMAL_NARX)
        
        # Balansga qo'shish
        bal = requests.get(f"{BASE_URL}balances/{d_id}.json").json() or 0
        requests.put(f"{BASE_URL}balances/{d_id}.json", json=bal + narx)
        
        res = f"🏁 **Safar yakunlandi!**\n📏 Masofa: `{dist}` km\n💰 Jami: **{narx:,}** so'm"
        await callback.message.edit_text(res, parse_mode="Markdown")
        await bot.send_message(c_id, res, parse_mode="Markdown")
        
        requests.delete(f"{BASE_URL}active_trips/{c_id}.json")
    await callback.answer()

# --- 6. STATISTIKA VA BALANS ---
@dp.message(Command("stat"))
async def get_stat(message: Message):
    if message.from_user.id == ADMIN_ID:
        bals = requests.get(f"{BASE_URL}balances.json").json() or {}
        trips = requests.get(f"{BASE_URL}active_trips.json").json() or {}
        total = sum(bals.values())
        await message.answer(f"📊 **Statistika:**\n🚖 Haydovchilar: {len(bals)}\n🔥 Aktiv: {len(trips)}\n💰 Aylanma: {total:,} so'm")

@dp.message(F.text == "💰 Mening balansim")
async def my_balance(message: Message):
    bal = requests.get(f"{BASE_URL}balances/{message.from_user.id}.json").json() or 0
    await message.answer(f"💰 Sizning balansingiz: **{bal:,}** so'm")

# --- 7. BEKOR QILISH ---
@dp.callback_query(F.data.startswith("d_cancel_"))
async def d_cancel(callback: types.CallbackQuery):
    c_id = int(callback.data.split("_")[2])
    requests.delete(f"{BASE_URL}active_trips/{c_id}.json")
    await callback.message.edit_text("❌ Bekor qilindi.")
    await bot.send_message(c_id, "😔 Haydovchi buyurtmani bekor qildi.")

async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

