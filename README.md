# PDF Storyteller 📖🎙️

A web application where users can upload storybook PDFs in **English** or **Bangla (বাংলা)** and listen to natural, expressive storytelling voice narrations with real-time text sync and karaoke highlighting.

---

## ✨ Features

- **Multilingual Support**:
  - **English**: Sentence splitting on punctuation (`.`, `?`, `!`) with storyteller voices (Christopher, Jenny, Guy, Aria, Sonia).
  - **Bangla (বাংলা)**: Sentence splitting respecting Bengali Dari (`।`), double Dari (`॥`), `?`, and `!` with authentic Bengali voices (`Pradeep`, `Nabanita`, `Bashkar`, `Tanishaa`).
- **Scanned PDF OCR Support**:
  - Automatic detection of scanned or image-based PDFs (documents with sparse/empty native text layers).
  - High-fidelity page rendering to images with PyMuPDF at **200 DPI**.
  - Multi-threaded OCR recognition via `pytesseract` (`ben+eng` for Bangla, `eng` for English).
  - Helpful user notification banner: *"This looks like a scanned PDF, text recognition may take longer and can contain errors."*
- **Optional AI Text Restoration (Anthropic Claude)**:
  - Toggle checkbox during upload: *"Improve text with AI (needs API key)"* (defaults to off).
  - Cleanly segments book text into ~3,000 character chunks respecting paragraph/line boundaries.
  - Restores broken words, OCR artifacts, and hyphenations using Claude while strictly preserving story content.
  - Safeguarded by strict 90%–110% length boundary validation; falls back to original text if exceeded.
  - Fast SHA-256 segment caching to disk (`backend/storage/cache/llm_clean/`) avoids duplicate API calls.
- **Cost & Size Warning and Character Tracking**:
  - Automatically calculates and stores total character count on the `Book` record immediately after extraction (and optional AI cleaning) and before TTS synthesis begins.
  - Displays document size in characters and estimated narration length (~900 chars/min) across the library, progress tracker, and audiobook player.
  - Proactively triggers a cost & size warning banner for large storybooks (>= 10,000 characters) to set expectations for processing time and API quota usage.
- **Extensible TTS Architecture**:
  - `TTSProvider` abstract base class with pluggable `EdgeTTSProvider` by default.
  - Can easily register OpenAI TTS, ElevenLabs, Google TTS, etc.
- **Dedicated Audio Storage**:
  - Audio files are stored strictly at: `backend/storage/<book_id>/chunk_XXX.mp3`.
- **Interactive Storybook Reader**:
  - Page-by-page narrative view with paragraph & sentence cards.
  - Click any sentence to play audio or synthesize on demand.
  - **"Narrate Entire Book"** batch synthesis with live progress.
  - Dynamic equalizer waveform indicator on active sentence.
  - Sticky bottom audio player dock with auto-advance, playback speed controls (`0.75x` to `2.0x`), volume, scrubber, and sentence preview.
- **Reading Themes**:
  - 🌙 **Midnight Dark**: Deep slate library theme with glowing indigo accents.
  - 📜 **Warm Sepia**: Classic book paper reading mode.
  - ☀️ **Clean Light**: Crisp editorial theme.

---

## 🛠️ Stack

- **Backend**: Python 3.11+, FastAPI, SQLite (SQLAlchemy), PyMuPDF (`pymupdf`), `pytesseract`, `Pillow`, `edge-tts`, `python-dotenv`.
- **Frontend**: React + Vite, Vanilla CSS with custom design system, `lucide-react`.

---

## 🔍 Tesseract OCR Installation (Scanned PDFs)

When a scanned or image-based PDF storybook is uploaded, the backend renders pages at 200 DPI and performs text recognition using Tesseract OCR. Follow the steps below for your operating system to install Tesseract and the Bangla language data:

### 🪟 Windows

1. **Install Tesseract OCR Engine**:
   - **Via Windows Package Manager (recommended)**:
     ```powershell
     winget install UB-Mannheim.TesseractOCR
     ```
   - **Or via Installer Executable**:
     Download the 64-bit installer from the UB-Mannheim repository:
     [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
     Run the `.exe` installer. In the installer wizard, under **"Additional language data (download)"**, check **"Bengali"** to automatically install Bangla data.

2. **Install Bangla Language Data (`ben.traineddata`) manually (if not selected during install)**:
   - Download `ben.traineddata` from the official Tesseract tessdata repository:
     [https://github.com/tesseract-ocr/tessdata_fast/raw/main/ben.traineddata](https://github.com/tesseract-ocr/tessdata_fast/raw/main/ben.traineddata)
   - Copy the downloaded `ben.traineddata` file into your Tesseract `tessdata` folder, typically:
     ```
     C:\Program Files\Tesseract-OCR\tessdata\ben.traineddata
     ```

3. **Configure Environment / PATH**:
   - Ensure `C:\Program Files\Tesseract-OCR` is added to your system `PATH`, **or** set the path in `backend/.env`:
     ```env
     TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
     ```

---

### 🍎 macOS

1. **Install Tesseract via Homebrew**:
   ```bash
   brew install tesseract
   ```

2. **Install Bangla Language Data**:
   ```bash
   brew install tesseract-lang
   ```
   *Alternatively*, download `ben.traineddata` directly into Homebrew's `tessdata` folder:
   - Apple Silicon (M1/M2/M3/M4):
     ```bash
     curl -L -o /opt/homebrew/share/tessdata/ben.traineddata https://github.com/tesseract-ocr/tessdata_fast/raw/main/ben.traineddata
     ```
   - Intel Macs:
     ```bash
     curl -L -o /usr/local/share/tessdata/ben.traineddata https://github.com/tesseract-ocr/tessdata_fast/raw/main/ben.traineddata
     ```

---

### 🐧 Ubuntu / Debian Linux

1. **Install Tesseract and Language Packs via APT**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y tesseract-ocr tesseract-ocr-ben tesseract-ocr-eng
   ```

---

### 🧪 Verify Tesseract Installation

Check that Tesseract is correctly installed and both `ben` (Bangla) and `eng` (English) are available:
```bash
tesseract --list-langs
```
Expected output:
```
List of installed languages (3):
ben
eng
osd
```

---

## 🤖 Anthropic Claude AI Cleanup (Optional)

To enable AI text improvement for scanned or imperfect PDFs:
1. Obtain an API key from [Anthropic Console](https://console.anthropic.com/).
2. Add your key to `backend/.env` (or copy from `backend/.env.example`):
   ```env
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ANTHROPIC_MODEL=claude-3-haiku-20240307
   ```
3. When uploading a book in the web app, check the **"Improve text with AI (needs API key)"** checkbox.
4. The system segments text into ~3,000 character chunks, runs the cleanup prompt, checks length sanity (90%–110%), and caches responses by segment hash so subsequent runs are instant and free. If no key is set or the API fails, it seamlessly falls back to standard regex cleanup.

---

## 🚀 How to Run

### 1. Start the Backend
Open a terminal in the project directory:

```powershell
# Activate Python virtual environment and set PYTHONPATH
$env:PYTHONPATH = "c:\Users\USER\Desktop\BOOK READER"
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The FastAPI API and Swagger docs will be available at:
- **API URL**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Start the Frontend
In a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Open your browser at:
- **Web App**: [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## 🧪 How to Test

Two pre-generated sample storybooks are available in `sample_books/`:
1. `sample_books/english_story_whispering_tree.pdf` (*The Whispering Tree and the Starlight Deer*)
2. `sample_books/bangla_story_blue_dove.pdf` (*ছোট্ট নীল ঘুঘু ও সোনালী নদী*)

### Testing via Web UI:
1. Open [http://127.0.0.1:5173](http://127.0.0.1:5173).
2. Upload a new PDF using the drag-and-drop uploader or select an existing book from the library.
3. Click **"Listen & Read"** on any storybook card.
4. Select a storytelling voice from the dropdown.
5. Click the **Play** button on any sentence to listen to the narration.
6. Check that the bottom audio player plays and automatically advances to the next sentence.

### Testing Audio File Storage:
Verify that synthesized audio files follow the requested path format:
```powershell
Get-ChildItem -Recurse "backend\storage\*\chunk_*.mp3"
```
Output pattern:
```
backend/storage/<book_id>/chunk_001.mp3
backend/storage/<book_id>/chunk_002.mp3
...
```
