# @muhammadjon_texno — avtomatik istoriyalar

Bu tizim GitHub Actions'da bepul ishlaydi va kompyuter o'chiq bo'lsa ham to'xtamaydi.

```
Claude (kontent + kartochka)  →  stories/  →  GitHub Actions (har 15 daqiqa)
                                               │ 09:30 / 18:30 da
                                               ▼
                                     Telegram bot: [✅ Chiqar] [⏭ Keyinroq] [❌ Bekor]
                                               │ ✅
                                               ▼
                                     Instagram istoriya (rasmiy API)
```

- Kuniga ko'pi bilan 2 ta istoriya, faqat 08:00–23:00 oralig'ida chiqadi.
- Hech bir istoriya sizning ✅ tasdig'ingizsiz chiqmaydi.
- Telegram buyruqlari: `/navbat` navbat holatini ko'rsatadi, `/hozir` keyingi istoriyani darhol yuboradi.
- Navbatda 3 tadan kam istoriya qolsa, bot ogohlantiradi.
- ⚠️ Instagram API so'rovnoma va havola stikerlarini qo'ya olmaydi. Shuning uchun so'rovnoma kartochkasida "Javobni DM'ga yozing" yozuvi turadi.

---

## Bir martalik sozlash (~20 daqiqa)

### 1-qadam. GitHub repo
1. https://github.com ga kiring (akkaunt bo'lmasa, bepul oching).
2. **New repository** tugmasini bosing. Nomi: `insta-stories`, turi: **Public**. Rasmlar baribir istoriyada hammaga ko'rinadi, maxfiy narsa yo'q. Tokenlar repoda saqlanmaydi.
3. Bu papkadagi barcha fayllarni repoga yuklang. `.github` papkasi ham yuklanishi shart.

### 2-qadam. Telegram bot
1. Telegram'da **@BotFather** ga yozing: `/newbot`, keyin nom bering (masalan `MT Stories`). U sizga **token** beradi, shuni saqlab qo'ying.
2. Yangi botingizni oching va **Start** bosing.
3. **@userinfobot** ga yozing. U sizning **ID** raqamingizni beradi.

### 3-qadam. Instagram tokeni
1. https://developers.facebook.com ga kiring va **Create App** bosing.
2. Use case sifatida **"Manage messaging & content on Instagram"** ni tanlang.
3. **API setup with Instagram login** bo'limida **Add account** bosing va @muhammadjon_texno bilan kiring.
4. **Generate token** bosing. Chiqqan uzun **token**ni saqlang. U 60 kun amal qiladi, keyin bot uni o'zi yangilaydi (5-qadamga qarang).

### 4-qadam. Maxfiy kalitlarni GitHub'ga kiritish
Repoda **Settings → Secrets and variables → Actions → New repository secret** ni oching va quyidagilarni qo'shing:

| Nomi | Qiymati |
|---|---|
| `TG_BOT_TOKEN` | 2-qadamdagi bot tokeni |
| `TG_CHAT_ID` | @userinfobot bergan ID |
| `IG_TOKEN` | 3-qadamdagi Instagram tokeni |

### 5-qadam (ixtiyoriy, lekin tavsiya). Tokenni avtomatik yangilash
1. GitHub'da **Settings (profil) → Developer settings → Fine-grained tokens → Generate new token** ni oching.
2. Repository access bo'limida faqat `insta-stories` ni tanlang. Permissions'da **Secrets: Read and write** ni yoqing.
3. Olingan tokenni `GH_PAT` nomi bilan secret sifatida qo'shing.

Bu qadamni qilmasangiz, Instagram tokeni eskirishidan ~10 kun oldin bot eslatma yuboradi. Shunda 3-qadamni takrorlab, `IG_TOKEN` ni yangilaysiz.

### 6-qadam. Sinov
1. Repoda **Actions → Instagram istoriya → Run workflow** ni bosing. Ishga tushirish yashil ✅ bilan tugashi kerak.
2. Telegram botga `/hozir` deb yozing.
3. Yana bir marta **Run workflow** bosing. Botga birinchi istoriya keladi.
4. ✅ ni bosing va yana **Run workflow** bosing. Istoriya Instagram'da paydo bo'ladi.

Shundan keyin hammasi o'zi ishlaydi. Faqat jadval bo'yicha kelgan istoriyalarga ✅ yoki ❌ bosib turasiz.

---

## Yangi kontent qo'shish (Claude qiladi)
```
"D:\AI Video Editor\tools\storyvenv\Scripts\python.exe" -X utf8 tools\make_cards.py content\<sana>.json
```
`content/*.json` faylidagi kontent `stories/<id>/story.jpg + meta.json` ko'rinishiga keladi. Keyin u repoga yuklanadi.
- Turlari: `fact`, `poll`, `reels` (muqova bilan "Yangi video" anonsi). `{so'z}` yozilgan joy urg'u rangida chiqadi.
- `"priority": 1` berilgan istoriya navbatning boshiga o'tadi. Bu yangi Reels anonsi uchun.

## Sozlamalar: `config.json`
| Kalit | Ma'nosi |
|---|---|
| `offer_times` | Telegram'ga tasdiq so'rovi yuboriladigan vaqtlar (Toshkent vaqti) |
| `max_per_day` | Kuniga eng ko'p nechta istoriya |
| `active_hours` | Instagram'ga chiqarish mumkin bo'lgan soatlar |
