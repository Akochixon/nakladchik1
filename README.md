# Накладнойларни raqamlashtirish boti

Distributor agentlar накладной (товарная накладная) rasmini Telegram botga
yuborsa, bot Google Gemini OCR yordamida hujjatni o'qiydi, agentga tasdiqlash
uchun ko'rsatadi va PostgreSQL bazasiga tuzilgan (structured) holda saqlaydi.

## Imkoniyatlar

- Yangi foydalanuvchini ro'yxatdan o'tkazish va admin tomonidan tasdiqlash/rad etish
- Накладной rasmini Gemini orqali tahlil qilish (hujjat №, sana, postavshik,
  xaridor, agent, tovarlar ro'yxati, jami summa)
- Agentga natijani ko'rsatib, tasdiqlash yoki xato maydonni qayta kiritish
- Bir xil hujjat raqami qayta yuborilsa, dublikat ekanini aniqlab, kim
  avval yuborganini ko'rsatish
- Admin uchun `/pending`, `/stats`, `/export` buyruqlari (CSV eksport)

## O'rnatish

1. `.env.example` faylini `.env` nomiga ko'chiring va qiymatlarni to'ldiring:
   - `BOT_TOKEN` — @BotFather dan
   - `ADMIN_IDS` — admin(lar)ning Telegram ID raqami(lari), vergul bilan
   - `DATABASE_URL` — PostgreSQL manzili (Railway avtomatik yaratadi)
   - `GEMINI_API_KEY` — https://aistudio.google.com/apikey dan bepul olinadi

2. Kutubxonalarni o'rnating:
   ```
   pip install -r requirements.txt
   ```

3. Botni ishga tushiring:
   ```
   python main.py
   ```
   Birinchi ishga tushishda jadvallar avtomatik yaratiladi.

## Railway'ga joylash

1. Loyihani GitHub'ga yuklang, so'ng Railway'da "Deploy from GitHub repo"
   tanlang.
2. Railway loyihasiga **PostgreSQL** plagini qo'shing — u avtomatik
   `DATABASE_URL` o'zgaruvchisini beradi (uni `postgresql+asyncpg://` prefiksiga
   moslashtiring, zarur bo'lsa `postgresql://`ni `postgresql+asyncpg://`ga
   almashtiring).
3. `BOT_TOKEN`, `ADMIN_IDS`, `GEMINI_API_KEY` environment variable'larini
   Railway loyihasiga qo'shing.
4. `Procfile` mavjud bo'lgani uchun Railway botni `worker` sifatida ishga
   tushiradi.

## Eslatma: rasm saqlash

Hozirgi versiyada накладной rasmi Telegramning o'z serverida (`file_id`
orqali) saqlanadi — alohida fayl xotirasi (Supabase Storage va h.k.) shart
emas. Agar rasmlarni tashqi joyda ham saqlash kerak bo'lsa, `handlers/user.py`
faylidagi `receive_invoice_photo` funksiyasida yuklab olingan fayl baytlarini
(`file_bytes`) tanlagan storage'ga yozish kifoya.

## Keyingi qadamlar (tavsiya)

- Admin uchun batafsil veb-panel (Railway/Vercel'da alohida joylashtirilishi
  mumkin)
- Har bir agent/mijoz bo'yicha qarz-hisobot (`/report` buyrug'i)
- OCR ishonchliligini oshirish uchun rasm sifatini tekshiruvchi qo'shimcha qadam
