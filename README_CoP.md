# 📋 CoP Lesson Learned AI

**An AI-powered web application that automatically transcribes Community of Practice (CoP) discussion recordings and generates complete official Lesson Learned reports in PUSDIKLAT KP format.**

Built during my internship as a Full-Stack Developer Intern at Pusdiklat Keuangan Publik, BPPK — Kementerian Keuangan RI (Mar–Jun 2026).

---

## ✨ Features

- 🎤 **Automatic Transcription** — Converts audio/video recordings to text using Groq Whisper large-v3, with auto-chunking and OGG Opus compression for large files
- 🤖 **AI Report Generation** — Analyzes the full transcript and auto-fills all 9 sections of the official CoP Lesson Learned report using Claude AI (Anthropic) or Groq LLaMA 3.3 70B as fallback
- ✍️ **AI Text Cleanup** — Refines raw transcription output with Claude AI or Groq before report generation
- 📄 **Transcript Import** — Accepts pre-existing transcripts from Microsoft Teams (VTT), Zoom, DOCX, and plain TXT — no re-recording needed
- 📝 **Official DOCX Output** — Generates formatted Word documents matching the official PUSDIKLAT KP CoP Lesson Learned structure, including letterhead logo and signature fields
- 📑 **PDF Export** — Converts DOCX to PDF via LibreOffice (optional)
- 🌐 **Single-Port Deployment** — Frontend served directly from the FastAPI backend at `http://localhost:8000`

---

## 🤖 AI-Generated Report Sections

The AI analyzes the full transcript and automatically fills all of the following sections:

| # | Section | Description |
|---|---|---|
| 1.1 | Executive Summary | Comprehensive overview of the discussion |
| 1.2 | Issue Statement | Core problem raised and its impact |
| 1.3 | Background | Context that led to the CoP session |
| 1.4 | Objectives | Goals of the discussion |
| 1.5 | Scope | Topics covered and participants involved |
| 3.1 | Pre-existing Policies | Regulations and policies mentioned in the discussion |
| 3.2.1 | Alternative Solutions | Proposed solutions and alternatives |
| 3.2.2 | Advantages & Disadvantages | Pros, cons, and challenges discussed |
| 3.2.3 | Key Learnings | Bullet-point insights extracted from the session |
| 4.1 | Conclusions | Summary of agreements and outcomes |
| 4.2 | Recommendations | Actionable follow-up steps |

> All sections are generated strictly from transcript content — the AI is instructed not to add information beyond what was actually discussed.

---

## 🛠️ Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Web Framework | FastAPI (Python) |
| Audio Processing | FFmpeg (conversion, chunking, compression) |
| Speech-to-Text | Groq Whisper large-v3 API |
| AI Report Generation | Anthropic Claude API (primary) / Groq LLaMA 3.3 70B (fallback) |
| AI Text Cleanup | Anthropic Claude Haiku / Groq LLaMA 3.3 70B |
| HTTP Client | httpx (with proxy & retry support) |

### Frontend
| Layer | Technology |
|---|---|
| UI | Vanilla HTML, CSS, JavaScript |
| Document Generation | Node.js + docx library (v9.6.1) |
| PDF Generation | LibreOffice (optional) |

---

## 🔄 How It Works

```
Upload Audio/Video  ──OR──  Upload Transcript (VTT/DOCX/TXT)
        │                              │
        ▼                              ▼
  FFmpeg → WAV 16kHz            Parse transcript
        │                         segments
        ▼
  Auto-split into chunks (5 min each)
  + Compress to OGG Opus
        │
        ▼
  Groq Whisper large-v3
  Transcription (per chunk, with retry)
        │
        ▼
  Claude AI / Groq — Text cleanup & correction
        │
        └──────────────────────────────────┘
                          │
                          ▼
             Claude AI / Groq LLaMA 3.3 70B
             Analyze full transcript →
             Auto-fill all 9 report sections
                          │
                          ▼
             Node.js + docx → .docx
             (PUSDIKLAT KP CoP format)
                          │
                    ┌─────┴─────┐
                    ▼           ▼
                 .docx       .pdf
                           (LibreOffice)
```

**AI provider priority:**
1. **Anthropic Claude Haiku** — primary for both cleanup and report generation
2. **Groq LLaMA 3.3 70B** — automatic fallback if Anthropic key is absent or unavailable

---

## 📁 Project Structure

```
cop-lessonlearned-ai/
├── main.py                ← FastAPI server & REST API endpoints (v4.0)
├── transcriber.py         ← Groq Whisper transcription (no diarization)
├── transcript_parser.py   ← Parse VTT / DOCX / TXT transcripts
├── generator.py           ← CoP DOCX generation via Node.js (v4.0)
├── index.html             ← Frontend UI
├── logo_kemenkeu.png      ← Official PUSDIKLAT KP letterhead logo
├── package.json           ← Node.js dependencies (docx ^9.6.1)
├── requirements.txt       ← Python dependencies
├── .env.example           ← Environment variable template
├── .env                   ← ⚠️ Create this yourself — never commit to Git
└── start.bat              ← One-click server start (Windows)
```

---

## 🚀 Getting Started

### Prerequisites

| Prerequisite | Check |
|---|---|
| Python 3.9+ | `python --version` |
| Node.js 18+ | `node --version` |
| FFmpeg | `ffmpeg -version` |

> **FFmpeg** is required for audio conversion. Download at https://www.gyan.dev/ffmpeg/builds/ and add to PATH.

### 1. Install Python dependencies
```bash
pip install fastapi uvicorn[standard] python-multipart python-dotenv httpx
```

### 2. Install Node.js dependencies
```bash
npm install
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in your API keys:

```env
# Required: at least one of these
GROQ_API_KEY=gsk_...             # https://console.groq.com (free)

# Optional but recommended: enables Claude AI for better report quality
ANTHROPIC_API_KEY=sk-ant-...     # https://console.anthropic.com

# Optional: for office networks with proxy
# HTTPS_PROXY=http://proxy.kantor.go.id:8080
```

> `ASSEMBLYAI_API_KEY` and `HF_TOKEN` are **not required** — this version uses Groq Whisper only, with no speaker diarization.

### 4. Run the server

**Windows:** double-click `start.bat`

**Or via terminal:**
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 600
```

### 5. Open the app

Go to **http://localhost:8000** in your browser.

> ⚠️ Do not open `index.html` directly — it must be served through the backend at port 8000.

---

## 🎯 Usage

### Mode 1 — Upload Recording

1. Select the **"Upload Rekaman"** tab
2. Upload an audio/video file (MP3 / WAV / MP4 / M4A / OGG / FLAC, up to 2GB)
3. Fill in CoP details: title, issue/problem, SK number, date, location, participants
4. Click **"Proses & Generate Dokumen"**
5. Wait for processing (typically 1–3 minutes per hour of audio)
6. Download the result as **Word (.docx)** or **PDF**

### Mode 2 — Upload Existing Transcript

Already have a transcript from Teams/Zoom?

1. Select the **"Upload Transkrip"** tab
2. Upload a `.vtt`, `.docx`, or `.txt` transcript file
3. Fill in CoP details and click process
4. The AI will generate the full report without re-processing audio

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serve frontend UI |
| `GET` | `/health` | Server health check |
| `POST` | `/transcribe` | Upload and transcribe audio, generate full report |
| `POST` | `/transcribe_local` | Transcribe a local file path (admin mode) |
| `POST` | `/transcript` | Generate report from an existing transcript file |
| `GET` | `/download/docx/{id}` | Download Word result |
| `GET` | `/download/pdf/{id}` | Download PDF result |

---

## 📄 Supported Transcript Formats

| Format | Source | Detected Pattern |
|---|---|---|
| `.vtt` | Microsoft Teams / Zoom | `<v Name>text` or `Name: text` with timestamps |
| `.txt` | Manual / any | `[00:01:23] Name: text`, `Name: text`, or timestamp variants |
| `.docx` | Word document | Paragraph-based, same patterns as TXT |

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ Required | Speech-to-text via Groq Whisper + AI fallback |
| `ANTHROPIC_API_KEY` | Recommended | Primary AI for text cleanup and report generation |
| `HTTPS_PROXY` | Optional | For office networks with proxy (e.g. `http://proxy.kemenkeu.go.id:8080`) |

---

## ⚠️ Notes

| Item | Detail |
|---|---|
| Processing time | ~1–3 minutes per hour of audio (cloud, no GPU needed) |
| Max file size | 2 GB |
| Audio chunking | Auto-split into 5-minute chunks + compressed to OGG Opus before upload |
| Groq rate limits | Handled automatically with retry and wait logic |
| Speaker labels | This version does not include speaker diarization — all speech is labeled "Pembicara" |
| PDF export | Requires LibreOffice installed and accessible from terminal |

---

## 🔒 Security Notes

- Never commit `.env` to Git — add it to `.gitignore`
- Uploaded audio files are automatically deleted after processing
- Output files are stored in `outputs/` — delete manually when no longer needed

---

## 👨‍💻 Author

**Muhammad Rafiif Dzakwan**
Full-Stack Developer Intern — Pusdiklat Keuangan Publik, BPPK, Kementerian Keuangan RI
[LinkedIn](https://www.linkedin.com/in/muhammad-rafiif-16b4a8245) · [Portfolio](https://rafiif-portofolio.vercel.app)
