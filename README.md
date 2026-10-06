# PDF Storyteller 📖🎙️

An expressive, full-stack storybook reader that converts **English** and **Bangla (বাংলা)** PDF storybooks into narrated audiobooks with real-time text synchronization, multi-provider neural text-to-speech, AI-powered text restoration, and multi-voice character casting.

---

## 🌟 Key Features

- **Multilingual Narration**:
  - **English**: Sentence splitting on punctuation (`.`, `?`, `!`) with neural voices (Christopher, Aria, Jenny, Guy, Sonia).
  - **Bangla (বাংলা)**: Sentence splitting respecting Bengali Dari (`।`), double Dari (`॥`), `?`, and `!`, with authentic Bengali voices (`Pradeep`, `Nabanita`, `Bashkar`, `Tanishaa`).
- **Dual TTS Provider Engine**:
  - **Microsoft Edge TTS (`edge_tts`)**: Free, high-quality neural voices with zero API key requirement, built-in retry backoff, and caching.
  - **ElevenLabs (`elevenlabs`)**: Ultra-expressive storytelling voices (Rachel, Adam, Antoni, Bella, Josh, Domi, Elli) via ElevenLabs REST API with automatic fallback and catalog queries.
- **Deduplicated Audio Caching**:
  - All synthesized chunks and segments are hashed using SHA-256 over `(text + voice + provider)`.
  - Cached files are persisted in `backend/storage/audio_cache/` so identical text segments are never synthesized twice.
- **Multi-Voice Character Narration**:
  - Character dialogue and narrator passages are tagged sentence-by-sentence via the Anthropic Claude API.
  - Deterministically maps characters to distinct voices from a language voice pool.
  - Slices and synthesizes per-speaker audio segments and concatenates them into seamless chapter audio using `pydub`.
- **Scanned PDF OCR Engine**:
  - Automatically identifies scanned or image-only PDFs with sparse native text layers.
  - Renders pages to 200 DPI images with PyMuPDF and runs parallel OCR via `pytesseract` (`ben+eng` for Bangla, `eng` for English).
  - Flags documents with a UI indicator and allows downstream AI restoration.
- **AI Text Cleanup (Anthropic Claude)**:
  - Fixes OCR artifacts, broken hyphenations, and scan noise.
  - Enforces strict 90%–110% output length boundaries to prevent content drift or summarization.
  - Caches cleaned segments by text hash in `backend/storage/.cache/`.
- **Granular Retry Engine**:
  - Endpoint `POST /api/books/{id}/retry` regenerates only failed or uncompleted chunks without reprocessing previously completed audio or re-extracting PDF pages.
  - Interactive "Retry Failed Chunks" action in both the library list and reader player.
- **Rich Audio Player & Reader**:
  - Sentence-by-sentence read-along with active sentence highlighting and auto-scroll.
  - Audio speed control (`0.75x`, `1.0x`, `1.25x`, `1.5x`, `2.0x`).
  - Next-chunk preloading for gapless listening.
  - Auto-resume and position persistence in `localStorage`.
  - System Media Session API integration for lock-screen, headphone, and notification controls.
  - Reading themes: **Midnight Dark**, **Warm Sepia**, and **Clean Light**.

---

## 🏗️ Architecture & Technology Stack

| Component | Technologies & Libraries |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn, SQLAlchemy, SQLite, PyMuPDF (`pymupdf`), `pytesseract`, `pillow`, `edge-tts`, `httpx`, `mutagen`, `anthropic`, `pydub`, `python-multipart`, `pytest` |
| **Frontend** | React 18, Vite, React Router 6, Vanilla CSS design system, `lucide-react` |
| **System Dependencies** | Tesseract OCR (with `ben` & `eng` traineddata), FFmpeg (for `pydub` audio processing) |

---

## 📋 Prerequisites

Before setting up the project, ensure you have the following installed on your system:

1. **Python**: Version **3.11 or higher** ([python.org](https://www.python.org/downloads/))
2. **Node.js**: Version **18 or higher** and `npm` ([nodejs.org](https://nodejs.org/))
3. **Tesseract OCR**: Required for scanned PDF text recognition.
4. **FFmpeg** *(Optional but recommended)*: Required by `pydub` for audio concatenation in multi-voice mode.

---

## ⚙️ System Dependencies Setup

### 1. Tesseract OCR Installation

#### 🪟 Windows:
1. Install Tesseract using `winget`:
   ```powershell
   winget install UB-Mannheim.TesseractOCR
   ```
   *(Or download the installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki). Ensure "Bengali" is checked under Additional language data).*
2. Verify or manually download `ben.traineddata`:
   - Download: [tessdata_fast/ben.traineddata](https://github.com/tesseract-ocr/tessdata_fast/raw/main/ben.traineddata)
   - Place into: `C:\Program Files\Tesseract-OCR\tessdata\ben.traineddata`
3. Ensure `C:\Program Files\Tesseract-OCR` is in your system `PATH`, or set `TESSERACT_CMD` in `backend/.env`:
   ```env
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

#### 🍎 macOS:
```bash
brew install tesseract tesseract-lang
```

#### 🐧 Linux (Ubuntu / Debian):
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-ben tesseract-ocr-eng
```

Verify Tesseract languages:
```bash
tesseract --list-langs
# Expected output includes: ben, eng, osd
```

---

### 2. FFmpeg Installation (for Multi-Voice Concatenation)

#### 🪟 Windows:
```powershell
winget install Gyan.FFmpeg
```
*(Verify by running `ffmpeg -version` in a new PowerShell window).*

#### 🍎 macOS:
```bash
brew install ffmpeg
```

#### 🐧 Linux (Ubuntu / Debian):
```bash
sudo apt-get install -y ffmpeg
```

---

## 🚀 Setup Steps: Backend

### 1. Navigate to the project root
```bash
cd "c:\Users\USER\Desktop\BOOK READER"
```

### 2. Create and activate a Python virtual environment
```powershell
# Windows PowerShell:
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1

# Linux / macOS:
python3 -m venv backend/.venv
source backend/.venv/bin/activate
```

### 3. Install Python dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Configure environment variables
Copy the example environment configuration:
```powershell
# Windows:
Copy-Item backend\.env.example backend\.env

# Linux / macOS:
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your preferred configurations:
```env
# Server
HOST=127.0.0.1
PORT=8000
DEBUG=True

# CORS
CORS_ORIGIN=http://localhost:5173

# Database & Storage
DATABASE_URL=sqlite:///./backend/storage/storyteller.db
STORAGE_DIR=backend/storage

# TTS Provider Defaults
DEFAULT_TTS_PROVIDER=edge_tts
DEFAULT_ENGLISH_VOICE=en-US-ChristopherNeural
DEFAULT_BANGLA_VOICE=bn-BD-PradeepNeural

# Optional: ElevenLabs TTS API Key
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Optional: Anthropic Claude API Key (for AI text cleanup & multi-voice casting)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 5. Start the FastAPI backend server
```powershell
# Windows (PowerShell):
$env:PYTHONPATH = (Get-Location).Path
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Linux / macOS:
export PYTHONPATH=$(pwd)
backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at:
- **API Base URL**: `http://127.0.0.1:8000`
- **Swagger Interactive Documentation**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

---

## 🎨 Setup Steps: Frontend

### 1. Open a new terminal and navigate to the frontend directory
```bash
cd frontend
```

### 2. Install Node dependencies
```bash
npm install
```

### 3. Configure frontend environment variables
Ensure `frontend/.env` contains your backend API URL:
```env
VITE_API_URL=http://127.0.0.1:8000
```
*(If missing, copy from `frontend/.env.example`)*:
```bash
cp .env.example .env
```

### 4. Start the frontend development server
```bash
npm run dev
```

Open your browser at:
- **Web Application**: `http://localhost:5173`

### 5. Build for production (Optional)
To validate or produce a production bundle:
```bash
npm run build
```
Output files will be generated in `frontend/dist/`.

---

## 🧪 Running Tests & Sample Books

### 1. Run Automated Test Suite
Run the comprehensive pytest suite covering API endpoints, models, chunking, OCR extraction, audio caching, and multi-voice synthesis:
```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -v
```

### 2. Test with Included Sample Storybooks
Pre-formatted sample storybooks are provided in `sample_books/`:
- `sample_books/english_story_whispering_tree.pdf` (*The Whispering Tree and the Starlight Deer*)
- `sample_books/bangla_story_blue_dove.pdf` (*ছোট্ট নীল ঘুঘু ও সোনালী নদী*)

Upload either PDF via the web UI at `http://localhost:5173` to test:
1. Normal text extraction and sentence chunking.
2. Voice preview and provider switching (`Edge TTS` vs `ElevenLabs`).
3. Multi-voice character toggle.
4. Real-time audio generation and playback.

---

## ⚠️ Known Limitations & Constraints

1. **Path Traversal & Directory Creation in Audio Endpoint**:
   - In `GET /api/audio/{book_id}/{filename}`, `book_id` is passed directly to `get_book_storage_dir(book_id)`, which runs `mkdir(parents=True, exist_ok=True)` without prior verification that `book_id` exists in the database.
   - The resolved file path is not currently validated using `.is_relative_to(STORAGE_DIR)` to enforce that requests cannot escape the designated storage directory.
2. **Multi-Voice Missing in Chunk Retry**:
   - The `retry_failed_chunks` background task calls `tts_provider.synthesize` with a single voice rather than checking `book.multi_voice` and routing through `synthesize_multivoice_chunk`. Retrying failed chunks on a multi-voice book reverts those specific chunks to single-voice audio.
3. **In-Process Background Task Execution & SQLite Concurrency**:
   - Book processing is queued using FastAPI's in-memory `BackgroundTasks`. Tasks do not survive server restarts, and tasks cannot be distributed across worker processes or multiple instances.
   - SQLite uses file-level locking (`WAL` mode is not explicitly configured), which can raise `database is locked` errors if multiple books are uploaded and processed simultaneously under high concurrency.
4. **Local Ephemeral File Storage**:
   - Uploaded PDFs and synthesized audio files are written directly to `backend/storage/`. In containerized environments (Docker, Kubernetes) without persistent volume mounts, stored books and audio files will be lost on container restart.
5. **OCR Resource Intensity & External Binary Dependency**:
   - Optical Character Recognition on large, high-resolution scanned PDFs (200 DPI) is CPU- and memory-intensive.
   - If Tesseract is not installed or `ben.traineddata` is missing on the host machine, scanned PDF uploads fail with an error.
6. **TTS Rate Limits & External API Quotas**:
   - Microsoft Edge TTS relies on Microsoft Edge's public WebSocket endpoint, which is subject to undocumented throttling or regional latency.
   - ElevenLabs and Anthropic Claude require valid API keys and paid usage tiers; processing long books (>= 10,000 characters) consumes significant quota.
7. **No Authentication or Multi-Tenant Isolation**:
   - The API currently lacks authentication, authorization, and tenant isolation; all uploaded books, audio chunks, and deletion endpoints are publicly accessible to anyone with network access to the API.
