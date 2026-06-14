"""
main.py v4.0 — FastAPI backend Lesson Learned CoP Penilaian BMD
PUSDIKLAT KP — format sesuai dokumen Lesson Learned CoP

Jalankan: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import os, uuid, shutil, json, httpx
from datetime import datetime
from dotenv import load_dotenv

from transcriber import transcribe_and_diarize
from transcript_parser import parse_transcript, get_speakers, get_duration
from generator import generate_docx, generate_pdf

load_dotenv(override=True)

app = FastAPI(
    title="Lesson Learned CoP API — PUSDIKLAT KP",
    version="4.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from starlette.middleware.base import BaseHTTPMiddleware

class LargeUploadMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.max_upload_size = 2 * 1024 * 1024 * 1024  # 2GB
        return await call_next(request)

app.add_middleware(LargeUploadMiddleware)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

HF_TOKEN = os.getenv("HF_TOKEN", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
print(f"[INIT] GROQ_KEY: {bool(GROQ_KEY)} | ANTHROPIC_KEY: {bool(ANTHROPIC_KEY)}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── HEALTH / ROOT ─────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h2>index.html tidak ditemukan</h2>", status_code=404)

@app.get("/health")
def health():
    return {"status": "✓ Lesson Learned CoP API v4.0 berjalan"}


# ── GENERATE ANALISIS CoP (isi semua bab dari transkripsi) ───────────────────
async def _call_llm(prompt: str, system: str, max_tokens: int = 1500) -> str:
    """Panggil LLM (Anthropic atau Groq sebagai fallback). Return teks atau string kosong."""
    if ANTHROPIC_KEY:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                for _model in ["claude-haiku-4-5-20251001", "claude-3-5-haiku-20241022"]:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                                 "Content-Type": "application/json"},
                        json={"model": _model, "max_tokens": max_tokens,
                              "system": system,
                              "messages": [{"role": "user", "content": prompt}]}
                    )
                    if resp.status_code == 200:
                        return resp.json()["content"][0]["text"].strip()
                    if resp.status_code != 404:
                        break
                err_body = ""
                try: err_body = resp.json().get("error", {}).get("message", "")
                except: pass
                print(f"      ⚠ Anthropic error: {resp.status_code} {err_body}")
        except Exception as e:
            print(f"      ⚠ Anthropic API error: {e}")

    if GROQ_KEY:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={"model": "llama-3.3-70b-versatile", "max_tokens": max_tokens,
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": prompt}]}
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
                print(f"      ⚠ Groq error: {resp.status_code}")
        except Exception as e:
            print(f"      ⚠ Groq API error: {e}")

    return ""


async def generate_analisis_cop(segments: list, judul_cop: str, isu_masalah: str) -> dict:
    """
    Analisis transkripsi CoP dengan AI dan hasilkan isian untuk SEMUA bab laporan.
    Return dict berisi konten per bab, atau dict kosong jika tidak ada API key.
    """
    if not ANTHROPIC_KEY and not GROQ_KEY:
        print("      ⚠ Tidak ada API key AI — bab laporan akan menggunakan teks default")
        return {}

    teks_diskusi = "\n".join([s.get("text", "") for s in segments if s.get("text")])
    if len(teks_diskusi.strip()) < 50:
        return {}

    # Potong transkripsi agar tidak melebihi batas token (~12000 karakter)
    teks_ringkas = teks_diskusi[:12000]
    if len(teks_diskusi) > 12000:
        teks_ringkas += "\n[...transkripsi dipotong...]"

    # System prompt NETRAL — tidak menyebut topik spesifik apapun
    system = (
        "Kamu adalah analis senior yang bertugas merangkum dan menganalisis transkripsi rekaman diskusi "
        "untuk laporan resmi Community of Practice (CoP) PUSDIKLAT KP Kementerian Keuangan RI. "
        "Tugasmu menghasilkan isian laporan resmi dalam Bahasa Indonesia formal yang LENGKAP, PANJANG, dan DETAIL "
        "HANYA berdasarkan isi transkripsi yang diberikan. "
        "DILARANG menambahkan informasi, topik, atau istilah yang tidak ada dalam transkripsi. "
        "DILARANG menggunakan label seperti 'PARAGRAF 1:', 'PARAGRAF 2:', 'Paragraf 1:', dsb. "
        "Setiap field harus berisi teks yang mengalir secara natural tanpa label paragraf apapun. "
        "Jawab HANYA dalam format JSON yang diminta, tanpa teks lain di luar JSON."
    )

    prompt = f"""Analisis transkripsi diskusi berikut dan isi setiap bagian laporan berdasarkan ISI TRANSKRIPSI SAJA.

Judul CoP: {judul_cop}
{f"Isu/Masalah: {isu_masalah}" if isu_masalah else ""}

TRANSKRIPSI:
{teks_ringkas}

Berikan output HANYA dalam format JSON berikut.
ATURAN WAJIB:
- Setiap field HANYA boleh berisi informasi yang BENAR-BENAR ADA dalam transkripsi di atas
- JANGAN menambah topik, istilah, atau konteks yang tidak disebutkan dalam transkripsi
- Jika suatu hal tidak dibahas dalam transkripsi, tulis "(tidak dibahas dalam rekaman)"
- Gunakan Bahasa Indonesia formal
- DILARANG menggunakan label "PARAGRAF 1", "PARAGRAF 2", "Paragraf 1:", "Paragraf 2:", atau sejenisnya
- Setiap field teks harus berupa paragraf yang mengalir mulus tanpa label apapun
- Isi setiap field harus PANJANG dan DETAIL — minimal 4-6 kalimat untuk field paragraf
- Untuk executive_summary, isu_masalah, latar_belakang, maksud_tujuan, ruang_lingkup, preexisting_policies, alternatif_masalah, keuntungan_kelemahan: tulis minimal 4-6 kalimat yang kaya detail dan konteks dari transkripsi
- Untuk pembelajaran_kunci: minimal 5 poin, masing-masing 2-3 kalimat penjelasan
- Untuk simpulan: minimal 4 poin, masing-masing 2 kalimat
- Untuk rekomendasi: minimal 4 poin, masing-masing 2 kalimat dengan langkah aksi konkret

{{
  "executive_summary": "4-6 kalimat mengalir merangkum secara menyeluruh apa yang dibahas, siapa yang terlibat, masalah apa yang diangkat, dan apa arah solusinya berdasarkan rekaman ini — tanpa label paragraf",
  "isu_masalah": "4-6 kalimat mengalir menjelaskan secara detail isu atau masalah utama yang diangkat, termasuk dampaknya dan kompleksitasnya berdasarkan rekaman — tanpa label paragraf",
  "latar_belakang": "4-6 kalimat mengalir tentang konteks lengkap dan latar belakang topik, termasuk kondisi yang mendorong diskusi ini sesuai yang disebutkan dalam rekaman — tanpa label paragraf",
  "maksud_tujuan": "4-6 kalimat mengalir tentang maksud penyelenggaraan dan tujuan spesifik yang ingin dicapai dari diskusi ini sesuai rekaman — tanpa label paragraf",
  "ruang_lingkup": "3-4 kalimat mengalir tentang cakupan tema, subtopik yang dibahas, peserta yang terlibat, dan batasan pembahasan dalam rekaman ini — tanpa label paragraf",
  "preexisting_policies": "4-6 kalimat mengalir tentang peraturan, regulasi, dan kebijakan yang DISEBUTKAN dalam rekaman beserta konteksnya (jika tidak ada tulis: tidak dibahas dalam rekaman) — tanpa label paragraf",
  "alternatif_masalah": "4-6 kalimat mengalir tentang berbagai solusi, alternatif, dan rekomendasi yang DIUSULKAN dalam rekaman beserta kelebihan masing-masing — tanpa label paragraf",
  "keuntungan_kelemahan": "4-6 kalimat mengalir menguraikan secara berimbang kelebihan, peluang, kelemahan, dan tantangan yang DIBAHAS dalam rekaman — tanpa label paragraf",
  "pembelajaran_kunci": ["poin kunci 1 — 2-3 kalimat penjelasan mendalam dari rekaman", "poin kunci 2 — 2-3 kalimat penjelasan mendalam", "poin kunci 3 — 2-3 kalimat penjelasan mendalam", "poin kunci 4 — 2-3 kalimat penjelasan mendalam", "poin kunci 5 — 2-3 kalimat penjelasan mendalam"],
  "simpulan": ["simpulan 1 — 2 kalimat dari rekaman", "simpulan 2 — 2 kalimat dari rekaman", "simpulan 3 — 2 kalimat dari rekaman", "simpulan 4 — 2 kalimat dari rekaman"],
  "rekomendasi": ["rekomendasi 1 — 2 kalimat dengan langkah aksi konkret", "rekomendasi 2 — 2 kalimat dengan langkah aksi konkret", "rekomendasi 3 — 2 kalimat dengan langkah aksi konkret", "rekomendasi 4 — 2 kalimat dengan langkah aksi konkret"]
}}"""

    print("[+] Menganalisis transkripsi dengan AI untuk mengisi semua bab laporan...")
    raw = await _call_llm(prompt, system, max_tokens=3500)

    if not raw:
        return {}

    # Parse JSON dari respons AI
    import re
    try:
        # Bersihkan markdown code block jika ada
        raw_clean = re.sub(r"```json\s*|```\s*", "", raw).strip()
        hasil = json.loads(raw_clean)
        print("    ✓ Analisis AI berhasil — semua bab terisi")
        return hasil
    except Exception as e:
        print(f"    ⚠ Gagal parse JSON analisis AI: {e}")
        # Coba ekstrak rekomendasi saja sebagai fallback
        return {}


# Fungsi lama dipertahankan untuk kompatibilitas (dipakai di /transcript endpoint)
async def generate_rekomendasi(segments: list, judul_cop: str, isu_masalah: str) -> str:
    """Wrapper: panggil generate_analisis_cop dan kembalikan rekomendasi sebagai teks."""
    hasil = await generate_analisis_cop(segments, judul_cop, isu_masalah)
    rek_list = hasil.get("rekomendasi", [])
    if rek_list:
        return "\n".join(f"{i+1}. {r}" for i, r in enumerate(rek_list))
    return ""


# ── TRANSCRIBE (dari audio/video) ─────────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(
    file:             UploadFile = File(...),
    perihal:          str = Form(default="LESSON LEARNED COMMUNITY OF PRACTICE"),
    dasar:            str = Form(default="-"),
    hari:             str = Form(default=""),
    tanggal:          str = Form(default=""),
    jam:              str = Form(default=""),
    tempat:           str = Form(default=""),
    agenda:           str = Form(default=""),
    jabatan_pejabat:  str = Form(default="Kepala Pusat Pendidikan Dan Pelatihan Keuangan Publik"),
    pejabat:          str = Form(default="................................"),
    notulis:          str = Form(default="................................"),
    peserta:          str = Form(default="[]"),
    # Field tambahan khusus CoP
    judul_cop:        str = Form(default=""),
    isu_masalah:      str = Form(default=""),
    nomor_sk:         str = Form(default=""),
):
    allowed_ext = [".mp3", ".wav", ".mp4", ".m4a", ".ogg", ".flac", ".mpeg"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Format tidak didukung.")

    file_id    = str(uuid.uuid4())
    audio_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    try:
        with open(audio_path, "wb") as f:
            chunk_size = 4 * 1024 * 1024
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        if os.path.exists(audio_path):
            os.remove(audio_path)
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {str(e)}")

    try:
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        print(f"\n{'='*50}\nAudio: {file.filename} | ID: {file_id} | Size: {file_size_mb:.1f} MB\n{'='*50}")

        try:
            peserta_list = json.loads(peserta)
        except Exception:
            peserta_list = []

        try:
            result = transcribe_and_diarize(audio_path, HF_TOKEN)
        except Exception as e:
            import traceback
            print(f"\nTRANSCRIBE ERROR:\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Transkripsi gagal: {str(e)}")

        print("[+] Menganalisis transkripsi dengan AI...")
        judul_final = judul_cop or perihal
        isu_final   = isu_masalah or agenda
        analisis = await generate_analisis_cop(result.get("segments", []), judul_final, isu_final)

        result = _inject_meta(result, perihal, dasar, hari, tanggal, jam, tempat, agenda,
                              jabatan_pejabat, pejabat, notulis, peserta_list, file_id,
                              analisis, judul_cop, isu_masalah, nomor_sk)

        docx_path = os.path.join(OUTPUT_DIR, f"cop_{file_id}.docx")
        generate_docx(result, docx_path)
        pdf_path = generate_pdf(docx_path, OUTPUT_DIR)

        return {"success": True, "file_id": file_id, "data": result, "has_pdf": pdf_path is not None}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


# ── TRANSCRIBE LOCAL ──────────────────────────────────────────────────────────
@app.post("/transcribe_local")
async def transcribe_local(
    local_path:       str = Form(...),
    perihal:          str = Form(default="LESSON LEARNED COMMUNITY OF PRACTICE"),
    dasar:            str = Form(default="-"),
    hari:             str = Form(default=""),
    tanggal:          str = Form(default=""),
    jam:              str = Form(default=""),
    tempat:           str = Form(default=""),
    agenda:           str = Form(default=""),
    jabatan_pejabat:  str = Form(default="Kepala Pusat Pendidikan Dan Pelatihan Keuangan Publik"),
    pejabat:          str = Form(default="................................"),
    notulis:          str = Form(default="................................"),
    peserta:          str = Form(default="[]"),
    judul_cop:        str = Form(default=""),
    isu_masalah:      str = Form(default=""),
    nomor_sk:         str = Form(default=""),
):
    if not os.path.exists(local_path):
        raise HTTPException(status_code=400, detail=f"File tidak ditemukan: {local_path}")

    allowed_ext = [".mp3", ".wav", ".mp4", ".m4a", ".ogg", ".flac", ".mpeg"]
    ext = os.path.splitext(local_path)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Format tidak didukung.")

    file_id = str(uuid.uuid4())
    try:
        print(f"\n{'='*50}\n[ADMIN] File Lokal: {local_path} | ID: {file_id}\n{'='*50}")
        try:
            peserta_list = json.loads(peserta)
        except Exception:
            peserta_list = []

        result = transcribe_and_diarize(local_path, HF_TOKEN)

        judul_final = judul_cop or perihal
        isu_final   = isu_masalah or agenda
        analisis = await generate_analisis_cop(result.get("segments", []), judul_final, isu_final)

        result = _inject_meta(result, perihal, dasar, hari, tanggal, jam, tempat, agenda,
                              jabatan_pejabat, pejabat, notulis, peserta_list, file_id,
                              analisis, judul_cop, isu_masalah, nomor_sk)

        docx_path = os.path.join(OUTPUT_DIR, f"cop_{file_id}.docx")
        generate_docx(result, docx_path)
        pdf_path = generate_pdf(docx_path, OUTPUT_DIR)

        return {"success": True, "file_id": file_id, "data": result, "has_pdf": pdf_path is not None}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── TRANSCRIPT (dari file teks) ───────────────────────────────────────────────
@app.post("/transcript")
async def from_transcript(
    file:             UploadFile = File(...),
    perihal:          str = Form(default="LESSON LEARNED COMMUNITY OF PRACTICE"),
    dasar:            str = Form(default="-"),
    hari:             str = Form(default=""),
    tanggal:          str = Form(default=""),
    jam:              str = Form(default=""),
    tempat:           str = Form(default=""),
    agenda:           str = Form(default=""),
    jabatan_pejabat:  str = Form(default="Kepala Pusat Pendidikan Dan Pelatihan Keuangan Publik"),
    pejabat:          str = Form(default="................................"),
    notulis:          str = Form(default="................................"),
    peserta:          str = Form(default="[]"),
    judul_cop:        str = Form(default=""),
    isu_masalah:      str = Form(default=""),
    nomor_sk:         str = Form(default=""),
):
    allowed_ext = [".txt", ".docx", ".vtt"]
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Format tidak didukung. Gunakan: TXT, DOCX, atau VTT.")

    file_id  = str(uuid.uuid4())
    tmp_path = os.path.join(UPLOAD_DIR, f"transcript_{file_id}{ext}")
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        print(f"\n{'='*50}\nTranskrip: {file.filename} | ID: {file_id}\n{'='*50}")
        print("[1/2] Parsing transkrip...")
        segments = parse_transcript(tmp_path)
        if not segments:
            raise ValueError("Tidak ada segmen yang berhasil di-parse.")

        speakers = get_speakers(segments)
        duration = get_duration(segments)
        print(f"      ✓ {len(segments)} segmen")

        try:
            peserta_list = json.loads(peserta)
        except Exception:
            peserta_list = []

        print("[2/2] Generate rekomendasi AI...")
        judul_final = judul_cop or perihal
        isu_final   = isu_masalah or agenda
        rekomendasi = await generate_rekomendasi(segments, judul_final, isu_final)

        result = {"segments": segments, "speakers": speakers,
                  "duration": duration, "language": "Bahasa Indonesia", "source": "transcript"}
        result = _inject_meta(result, perihal, dasar, hari, tanggal, jam, tempat, agenda,
                              jabatan_pejabat, pejabat, notulis, peserta_list, file_id,
                              rekomendasi, judul_cop, isu_masalah, nomor_sk)

        docx_path = os.path.join(OUTPUT_DIR, f"cop_{file_id}.docx")
        generate_docx(result, docx_path)
        pdf_path = generate_pdf(docx_path, OUTPUT_DIR)

        print(f"✓ SELESAI — {len(segments)} segmen")
        return {"success": True, "file_id": file_id, "data": result, "has_pdf": pdf_path is not None}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ── DOWNLOAD ──────────────────────────────────────────────────────────────────
@app.get("/download/docx/{file_id}")
def download_docx(file_id: str):
    path = os.path.join(OUTPUT_DIR, f"cop_{file_id}.docx")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File DOCX tidak ditemukan.")
    ts = datetime.now().strftime("%Y%m%d")
    return FileResponse(path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"LessonLearned_CoP_{ts}.docx")


@app.get("/download/pdf/{file_id}")
def download_pdf(file_id: str):
    path = os.path.join(OUTPUT_DIR, f"cop_{file_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File PDF tidak ditemukan.")
    ts = datetime.now().strftime("%Y%m%d")
    return FileResponse(path, media_type="application/pdf", filename=f"LessonLearned_CoP_{ts}.pdf")


# ── HELPER ─────────────────────────────────────────────────────────────────────
def _inject_meta(result, perihal, dasar, hari, tanggal, jam, tempat, agenda,
                 jabatan_pejabat, pejabat, notulis, peserta_list, file_id,
                 analisis=None, judul_cop="", isu_masalah="", nomor_sk=""):
    # analisis bisa berupa dict (dari generate_analisis_cop) atau string lama (dari /transcript)
    if isinstance(analisis, str):
        analisis = {"rekomendasi": [l.lstrip("0123456789. ") for l in analisis.split("\n") if l.strip()]}
    analisis = analisis or {}

    result["perihal"]          = perihal
    result["dasar"]            = dasar
    result["hari"]             = hari
    result["tanggal"]          = tanggal or datetime.now().strftime("%d %B %Y")
    result["jam"]              = jam
    result["tempat"]           = tempat
    result["agenda_text"]      = agenda
    result["jabatan_pejabat"]  = jabatan_pejabat
    result["pejabat"]          = pejabat
    result["notulis"]          = notulis
    result["file_id"]          = file_id
    result["peserta_list"]     = peserta_list
    result["judul_cop"]        = judul_cop or perihal
    result["isu_masalah"]      = isu_masalah or analisis.get("isu_masalah", "")
    result["nomor_sk"]         = nomor_sk
    # Simpan seluruh hasil analisis AI ke result agar generator.py bisa pakai semua bab
    result["analisis_ai"]      = analisis
    # Kompatibilitas frontend lama
    rek_list = analisis.get("rekomendasi", [])
    result["rekomendasi"]      = "\n".join(f"{i+1}. {r}" for i, r in enumerate(rek_list))
    result["kesimpulan"]       = result["rekomendasi"]
    return result