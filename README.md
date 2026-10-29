# Ron — AI Instagram Carousel Agent 🚀

A cloud-native Telegram bot that turns raw user photos and topics into viral, studio-grade 5-slide Instagram Carousels (1080×1350) in seconds.

## ✨ Features
- **Smart 4-Photo Combo Cover**: When 4+ photos are sent, automatically generates a 2×2 split grid cover with the signature horizontal seam headline.
- **Zero Face Obstruction & Strategic Framing**: Face is kept crystal clear in the upper 30%, while the text overlay and dark gradient sit over the lower third/midriff.
- **2–3 Lines Max Copy**: Powered by **Google Gemini 2.5 Flash** for concise, high-impact financial & wealth education copy with bold highlights.
- **Studio Typography**: `#FFDE43` warm gold + deep pine/dark charcoal contrast.
- **Special Commands vs Normal Chat**:
  - Normal Chat: Casual friendly chat and idea bouncing.
  - `#make <heading>` or `#banao <heading>`: Triggers high-res rendering.
  - `#inst <instruction>`: Locks custom guidelines into memory.
  - `#status` & `#clear`: Check or reset buffer.
- **Dual Export**: Sends an Instagram Photo Album + uncompressed high-resolution PNG document files.

---

## 🛠️ Project Structure
```
carousel_agent_bot/
├── bot.py             # Telegram bot handler & media group collector
├── ai_writer.py       # Gemini 2.5 Flash integration & copywriting prompt
├── renderer.py        # Playwright 1080x1350 headless Chrome renderer
├── requirements.txt   # Dependencies
├── Dockerfile         # Production container (Pre-packaged with Playwright & Chromium)
├── .env.example       # Example environment configuration
└── README.md
```

---

## 💻 Local Quickstart
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Start the bot:
   ```bash
   python bot.py
   ```
3. Open Telegram and search for `@ronymyassistant_bot`. Send `/start`, then send 4 photos with your topic in the caption!

---

## ☁️ 24/7 Cloud Deployment (GitHub + Railway / Render)

### Step 1: Push to GitHub
```bash
git add .
git commit -m "feat: Initial Ron Carousel Bot"
git push -u origin main
```

### Step 2: Deploy in 1 Click on Railway (Recommended)
1. Go to [Railway.app](https://railway.app) and sign in with GitHub.
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select `yasha161/tgbot`.
4. Go to **Variables** tab and add:
   - `TELEGRAM_BOT_TOKEN = <your_telegram_bot_token>`
   - `GEMINI_API_KEY = <your_gemini_api_key>`
5. Click **Deploy**. Railway will build the Docker container and your bot will run 24/7 in the cloud!
