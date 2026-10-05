# PDF Storyteller 📖🎙️

A web application where users can upload storybook PDFs in **English** or **Bangla (বাংলা)** and listen to natural, expressive storytelling voice narrations with real-time text sync and karaoke highlighting.

---

## ✨ Features

- **Multilingual Support**:
  - **English**: Sentence splitting on punctuation (`.`, `?`, `!`) with storyteller voices (Christopher, Jenny, Guy, Aria, Sonia).
  - **Bangla (বাংলা)**: Sentence splitting respecting Bengali Dari (`।`), double Dari (`॥`), `?`, and `!` with authentic Bengali voices (`Pradeep`, `Nabanita`, `Bashkar`, `Tanishaa`).
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

- **Backend**: Python 3.11+, FastAPI, SQLite (SQLAlchemy), PyMuPDF (`pymupdf`), `edge-tts`, `python-dotenv`.
- **Frontend**: React + Vite, Vanilla CSS with custom design system, `lucide-react`.

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
