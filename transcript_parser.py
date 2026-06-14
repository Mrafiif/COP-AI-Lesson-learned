"""
transcript_parser.py
Parse berbagai format transkrip teks menjadi format segmen standar NotulaAI.
Support: TXT, DOCX, VTT (Microsoft Teams / Zoom)
"""
import re
import os
from datetime import timedelta


# ── FORMAT STANDAR OUTPUT ─────────────────────────────────────────────────────
# Setiap segmen: {"start": "00:01", "end": "00:05", "speaker": "Nama", "text": "..."}

def parse_transcript(file_path: str) -> list:
    """
    Auto-detect format dan parse transkrip.
    Bisa mendeteksi VTT dari konten meski ekstensi .txt.
    Return: list of segments dalam format standar.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.docx':
        return parse_docx(file_path)

    # Untuk .vtt dan .txt: deteksi dari konten
    if ext in ('.vtt', '.txt'):
        try:
            with open(file_path, encoding='utf-8-sig') as f:
                preview = f.read(500)
        except Exception:
            preview = ''

        is_vtt = (
            'WEBVTT' in preview or
            ('-->' in preview and ('<v ' in preview or bool(re.search(r'\d{2}:\d{2}:\d{2}', preview))))
        )

        if is_vtt:
            return parse_vtt(file_path)
        else:
            return parse_txt(file_path)

    raise ValueError(f"Format tidak didukung: {ext}. Gunakan VTT, DOCX, atau TXT.")


# ── VTT PARSER (Microsoft Teams / Zoom) ──────────────────────────────────────
def parse_vtt(file_path: str) -> list:
    """
    Parse file WebVTT (.vtt) dari Microsoft Teams atau Zoom.

    Format Teams:
        00:00:01.000 --> 00:00:05.000
        <v Budi Santoso>Selamat pagi semua

    Format Zoom:
        00:00:01.000 --> 00:00:05.000
        Budi Santoso: Selamat pagi semua
    """
    with open(file_path, encoding='utf-8-sig') as f:
        content = f.read()

    segments = []
    # Split per blok cue
    blocks = re.split(r'\n\s*\n', content.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Cari baris timestamp
        timestamp_line = None
        text_lines     = []
        for i, line in enumerate(lines):
            if '-->' in line:
                timestamp_line = line
                text_lines     = lines[i+1:]
                break

        if not timestamp_line or not text_lines:
            continue

        # Parse timestamp
        m = re.search(r'(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})', timestamp_line)
        if not m:
            # Coba format mm:ss
            m = re.search(r'(\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{2}:\d{2}[\.,]\d{3})', timestamp_line)
        if not m:
            continue

        start_str = m.group(1).replace(',', '.')
        end_str   = m.group(2).replace(',', '.')
        start_fmt = _vtt_time_to_display(start_str)
        end_fmt   = _vtt_time_to_display(end_str)

        # Gabungkan teks
        full_text = ' '.join(text_lines).strip()
        if not full_text:
            continue

        # Deteksi pembicara
        # Format Teams: <v Nama>teks
        speaker, text = _extract_speaker_vtt(full_text)

        segments.append({
            "start":   start_fmt,
            "end":     end_fmt,
            "speaker": speaker,
            "text":    text.strip()
        })

    # Merge segmen pembicara yang sama berurutan
    return _merge_consecutive(segments)


def _vtt_time_to_display(ts: str) -> str:
    """Konversi '00:01:23.456' atau '01:23.456' ke '01:23'"""
    parts = ts.split('.')
    time_part = parts[0]  # '00:01:23' atau '01:23'
    components = time_part.split(':')
    if len(components) == 3:
        h, m, s = int(components[0]), int(components[1]), int(components[2])
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    elif len(components) == 2:
        m, s = int(components[0]), int(components[1])
        return f"{m:02d}:{s:02d}"
    return time_part


def _extract_speaker_vtt(text: str):
    """Extract nama pembicara dari berbagai format VTT."""
    # Format Teams: <v Nama Lengkap>teks
    m = re.match(r'<v\s+([^>]+)>(.*)', text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Format Zoom/generic: "Nama: teks"
    m = re.match(r'^([A-Za-z][^:]{2,40}):\s*(.*)', text, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    return "Pembicara", text


# ── TXT PARSER ────────────────────────────────────────────────────────────────
def parse_txt(file_path: str) -> list:
    """
    Parse plain text transkrip.

    Format yang didukung:
    1. [00:01:23] Nama: teks
    2. (00:01:23) Nama: teks
    3. 00:01:23 - Nama: teks
    4. Nama: teks  (tanpa timestamp)
    5. Nama (00:01): teks
    """
    with open(file_path, encoding='utf-8-sig') as f:
        lines = f.readlines()

    segments = []
    current = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parsed = _parse_txt_line(line)
        if parsed:
            if current:
                segments.append(current)
            current = parsed
        elif current:
            # Lanjutan teks dari baris sebelumnya
            current["text"] += " " + line

    if current:
        segments.append(current)

    # Isi end time dari start berikutnya
    for i in range(len(segments) - 1):
        if segments[i]["end"] == "—":
            segments[i]["end"] = segments[i+1]["start"]
    if segments and segments[-1]["end"] == "—":
        segments[-1]["end"] = segments[-1]["start"]

    return _merge_consecutive(segments)


def _parse_txt_line(line: str):
    """Coba parse satu baris teks transkrip."""
    # Pattern 1: [HH:MM:SS] atau [MM:SS] Nama: teks
    m = re.match(r'[\[\(](\d{1,2}:\d{2}(?::\d{2})?)[\]\)]\s*([^:]+):\s*(.*)', line)
    if m:
        return {"start": _normalize_time(m.group(1)), "end": "—",
                "speaker": m.group(2).strip(), "text": m.group(3).strip()}

    # Pattern 2: HH:MM:SS - Nama: teks
    m = re.match(r'(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*([^:]+):\s*(.*)', line)
    if m:
        return {"start": _normalize_time(m.group(1)), "end": "—",
                "speaker": m.group(2).strip(), "text": m.group(3).strip()}

    # Pattern 3: Nama (HH:MM): teks
    m = re.match(r'([^(]+)\s*\((\d{1,2}:\d{2}(?::\d{2})?)\)\s*:\s*(.*)', line)
    if m:
        return {"start": _normalize_time(m.group(2)), "end": "—",
                "speaker": m.group(1).strip(), "text": m.group(3).strip()}

    # Pattern 4: Nama: teks (tanpa timestamp)
    m = re.match(r'^([A-Za-z][^:]{2,50}):\s+(.+)', line)
    if m and len(m.group(2)) > 2:
        return {"start": "—", "end": "—",
                "speaker": m.group(1).strip(), "text": m.group(2).strip()}

    return None


def _normalize_time(ts: str) -> str:
    """Normalisasi format waktu ke MM:SS atau HH:MM:SS."""
    parts = ts.split(':')
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    elif len(parts) == 3:
        h = int(parts[0])
        if h > 0:
            return f"{h:02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
        return f"{int(parts[1]):02d}:{int(parts[2]):02d}"
    return ts


# ── DOCX PARSER ───────────────────────────────────────────────────────────────
def parse_docx(file_path: str) -> list:
    """
    Parse transkrip dari file Word (.docx).
    Support format Teams export dan format manual.
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError("Library 'python-docx' belum terinstall. Jalankan: pip install python-docx")

    doc   = Document(file_path)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    # Coba parse tiap baris dengan logika yang sama seperti TXT
    segments = []
    current  = None

    for line in lines:
        parsed = _parse_txt_line(line)
        if parsed:
            if current:
                segments.append(current)
            current = parsed
        elif current:
            current["text"] += " " + line

    if current:
        segments.append(current)

    # Isi end time
    for i in range(len(segments) - 1):
        if segments[i]["end"] == "—":
            segments[i]["end"] = segments[i+1]["start"]
    if segments and segments[-1]["end"] == "—":
        segments[-1]["end"] = segments[-1]["start"]

    return _merge_consecutive(segments)


# ── HELPERS ───────────────────────────────────────────────────────────────────
def _merge_consecutive(segments: list) -> list:
    """Gabungkan segmen berurutan dari pembicara yang sama."""
    if not segments:
        return []
    merged = [segments[0].copy()]
    for seg in segments[1:]:
        if seg["speaker"] == merged[-1]["speaker"] and seg["text"]:
            merged[-1]["text"] += " " + seg["text"]
            merged[-1]["end"]   = seg["end"]
        else:
            merged.append(seg.copy())
    return merged


def get_speakers(segments: list) -> list:
    """Ambil daftar pembicara unik dari segmen."""
    seen = []
    for s in segments:
        if s["speaker"] not in seen:
            seen.append(s["speaker"])
    return seen


def get_duration(segments: list) -> str:
    """Estimasi durasi dari segmen terakhir."""
    if not segments:
        return "00:00"
    last_end = segments[-1].get("end") or segments[-1].get("start", "00:00")
    return last_end if last_end != "—" else "—"