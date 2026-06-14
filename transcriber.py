"""
transcriber.py — Groq Whisper Only (tanpa diarization)
=========================================================
Transkripsi audio menggunakan Groq Whisper large-v3.
Tidak ada speaker diarization.

Variabel .env yang dibutuhkan:
    GROQ_API_KEY       = gsk_...   (wajib untuk transkripsi)
    ANTHROPIC_API_KEY  = ...       (opsional, untuk cleanup teks)
    HTTPS_PROXY        = http://...  (opsional, jika pakai proxy)
"""

import os, json, shutil, subprocess, tempfile, time, wave
import array as _array
from datetime import timedelta

GROQ_KEY      = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

_PROXY_URL = (
    os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or
    os.getenv("HTTP_PROXY")  or os.getenv("http_proxy") or None
)

WHISPER_PROMPT = (
    "Ini adalah rekaman diskusi Community of Practice (CoP) Penilaian Barang Milik Daerah (BMD) "
    "yang diselenggarakan oleh PUSDIKLAT KP Kementerian Keuangan Republik Indonesia. "
    "Bahasa Indonesia formal dengan istilah: BMD, BPKAD, BPK, APIP, Permendagri, "
    "penghapusan aset, kendaraan dinas, rusak berat, lesson learned, CoP, Samsat, penilaian properti."
)


def _get_http_client(timeout: int = 120, write_timeout: int = None):
    import httpx
    wt = write_timeout if write_timeout is not None else timeout * 2
    proxy_mounts = None
    if _PROXY_URL:
        print(f"      [HTTP] Menggunakan proxy: {_PROXY_URL}")
        proxy_mounts = {
            "https://": httpx.HTTPTransport(proxy=_PROXY_URL, retries=3),
            "http://":  httpx.HTTPTransport(proxy=_PROXY_URL, retries=3),
        }
    transport = httpx.HTTPTransport(retries=3) if not proxy_mounts else None
    t = httpx.Timeout(connect=60, write=wt, read=timeout, pool=30)
    if proxy_mounts:
        return httpx.Client(mounts=proxy_mounts, timeout=t, follow_redirects=True, verify=False)
    return httpx.Client(transport=transport, timeout=t, follow_redirects=True)


def format_time(seconds: float) -> str:
    td    = timedelta(seconds=max(0, seconds))
    total = int(td.total_seconds())
    h, m, s = total // 3600, (total % 3600) // 60, total % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    for path in [
        r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]:
        if os.path.exists(path):
            return path
    return None


def convert_to_wav(input_path: str, output_path: str = None) -> str:
    if output_path is None:
        # Pakai tempfile agar tidak bergantung pada direktori input
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix="_conv.wav", delete=False)
        output_path = tmp.name
        tmp.close()
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("FFmpeg tidak ditemukan!")
    ext = os.path.splitext(input_path)[1].lower()
    cmd = [ffmpeg, "-i", input_path]
    if ext in [".mp4", ".avi", ".mkv", ".mov", ".wmv"]:
        cmd += ["-vn"]
    cmd += ["-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_path, "-y"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{result.stderr[-500:]}")
    return output_path


def _compress_chunk_for_groq(wav_chunk_path: str) -> tuple:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return wav_chunk_path, "audio/wav", ".wav"
    ogg_path = wav_chunk_path.replace(".wav", ".ogg")
    try:
        r = subprocess.run(
            [ffmpeg, "-i", wav_chunk_path, "-c:a", "libopus", "-b:a", "32k", "-vbr", "on", ogg_path, "-y"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0 and os.path.exists(ogg_path):
            wav_mb = os.path.getsize(wav_chunk_path) / 1024 / 1024
            ogg_mb = os.path.getsize(ogg_path) / 1024 / 1024
            print(f"        Kompres: {wav_mb:.1f}MB WAV → {ogg_mb:.1f}MB OGG")
            os.remove(wav_chunk_path)
            return ogg_path, "audio/ogg", ".ogg"
    except Exception as e:
        print(f"        ⚠ Kompres gagal ({e})")
    return wav_chunk_path, "audio/wav", ".wav"


def _split_wav_chunks(wav_path: str, chunk_minutes: int = 5) -> list:
    with wave.open(wav_path, "rb") as wf:
        n_ch, fr = wf.getnchannels(), wf.getframerate()
        data     = wf.readframes(wf.getnframes())
        durasi   = wf.getnframes() / fr
    samples = _array.array("h", data)
    if n_ch > 1:
        samples = samples[::n_ch]
    chunk_sec, chunks, offset = chunk_minutes * 60, [], 0.0
    while offset < durasi:
        end_s         = min(durasi, offset + chunk_sec)
        chunk_samples = samples[int(offset * fr):int(end_s * fr)]
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        with wave.open(tmp_path, "wb") as wout:
            wout.setnchannels(1); wout.setsampwidth(2); wout.setframerate(fr)
            wout.writeframes(_array.array("h", chunk_samples).tobytes())
        size_mb = os.path.getsize(tmp_path) / 1024 / 1024
        print(f"      Chunk {len(chunks)+1}: {offset/60:.1f}-{end_s/60:.1f} mnt ({size_mb:.1f} MB)")
        chunks.append((tmp_path, offset))
        offset = end_s
    return chunks


def transcribe_with_groq(wav_path: str, groq_key: str) -> list:
    import httpx
    with wave.open(wav_path, "rb") as wf:
        durasi = wf.getnframes() / wf.getframerate()
    print(f"      Durasi audio: {durasi/60:.1f} menit")

    # Test koneksi
    try:
        client = _get_http_client(timeout=15)
        resp   = client.get("https://api.groq.com/openai/v1/models",
                            headers={"Authorization": f"Bearer {groq_key}"})
        if resp.status_code == 200:
            print("      ✓ Koneksi ke Groq berhasil")
        else:
            raise ConnectionError(f"Groq merespons status: {resp.status_code}")
    except Exception as e:
        raise ConnectionError(f"Tidak bisa terhubung ke Groq: {e}")

    chunks, all_segments = _split_wav_chunks(wav_path), []

    for i, (chunk_path, offset) in enumerate(chunks):
        compressed_path = chunk_path
        try:
            print(f"      Mengirim chunk {i+1}/{len(chunks)} ke Groq...")
            compressed_path, mime_type, chunk_ext = _compress_chunk_for_groq(chunk_path)
            chunk_filename = f"chunk_{i}{chunk_ext}"
            last_error, result = None, None

            for attempt in range(3):
                try:
                    client = _get_http_client(timeout=300, write_timeout=600)
                    with open(compressed_path, "rb") as f:
                        resp = client.post(
                            "https://api.groq.com/openai/v1/audio/transcriptions",
                            headers={"Authorization": f"Bearer {groq_key}"},
                            files={"file": (chunk_filename, f, mime_type)},
                            data={"model": "whisper-large-v3", "language": "id",
                                  "response_format": "verbose_json", "prompt": WHISPER_PROMPT},
                        )
                    if resp.status_code == 429:
                        import re as _re
                        msg = resp.text
                        wm = _re.search(r'try again in (\d+)m(\d+\.?\d*)s', msg)
                        ws = int(wm.group(1))*60 + float(wm.group(2)) + 5 if wm else 125
                        print(f"      ⏳ Rate limit — tunggu {int(ws)}s...")
                        time.sleep(int(ws)); last_error = RuntimeError("rate limit"); continue
                    if resp.status_code != 200:
                        raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text[:200]}")
                    result = resp.json(); last_error = None; break
                except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
                    last_error = e
                    wait = (attempt + 1) * 10
                    print(f"      ⚠ attempt {attempt+1} gagal: {type(e).__name__} — retry {wait}s...")
                    time.sleep(wait)
                except Exception as e:
                    last_error = e; break

            if last_error or result is None:
                print(f"      ✗ Chunk {i+1} gagal: {last_error}"); continue

            segs = result.get("segments", [])
            if not segs and result.get("text"):
                segs = [{"start": 0, "end": durasi / max(1, len(chunks)), "text": result["text"]}]
            for seg in segs:
                text = seg.get("text", "").strip()
                if text:
                    all_segments.append({
                        "start": seg.get("start", 0) + offset,
                        "end":   seg.get("end",   0) + offset,
                        "text":  text,
                    })
            print(f"      ✓ Chunk {i+1}: {len(segs)} segmen")

        except Exception as e:
            print(f"      ⚠ Chunk {i+1} error: {e}")
        finally:
            for p in set([chunk_path, compressed_path]):
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except: pass

    print(f"      ✓ Total: {len(all_segments)} segmen")
    return all_segments


def _cleanup_text(text: str) -> str:
    import re
    text = re.sub(r"\[.*?\]", "", text.strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text[0].upper() + text[1:] if text else text


def _rapikan_dengan_claude_batch(segments_text: list, api_key: str) -> list:
    system_prompt = (
        "Kamu adalah editor transkripsi rapat CoP Penilaian BMD PUSDIKLAT KP. "
        "Perbaiki transkripsi otomatis tanpa mengubah makna. Ikuti instruksi ketat."
    )
    user_template = (
        "Perbaiki transkripsi otomatis berikut.\n"
        "ATURAN: (1) Perbaiki salah transkripsi (2) Perbaiki ejaan & tanda baca "
        "(3) Pertahankan format [nomor] (4) Balas HANYA teks perbaikan.\n"
        "Istilah: BMD, BPKAD, BPK, APIP, Permendagri, CoP, PUSDIKLAT, KP, Samsat, rusak berat.\n\n{combined}"
    )
    all_results = list(segments_text)
    for batch_start in range(0, len(segments_text), 20):
        batch    = segments_text[batch_start:batch_start + 20]
        numbered = [f"[{batch_start + i + 1}] {t}" for i, t in enumerate(batch)]
        try:
            client = _get_http_client(timeout=60)
            for _model in ["claude-haiku-4-5-20251001", "claude-3-5-haiku-20241022"]:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    json={"model": _model, "max_tokens": 4000,
                          "system": system_prompt,
                          "messages": [{"role": "user", "content": user_template.format(combined="\n".join(numbered))}]},
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
                if resp.status_code != 404:
                    break  # gunakan respons ini (200 atau error lain)
            if resp.status_code != 200:
                err_body = ""
                try: err_body = resp.json().get("error", {}).get("message", resp.text[:200])
                except: err_body = resp.text[:200]
                raise RuntimeError(f"Claude HTTP {resp.status_code}: {err_body}")
            for line in resp.json()["content"][0]["text"].strip().split("\n"):
                line = line.strip()
                if line.startswith("[") and "]" in line:
                    try:
                        be = line.index("]"); num = int(line[1:be]); txt = line[be+1:].strip()
                        if txt and 1 <= num <= len(segments_text):
                            all_results[num - 1] = txt
                    except: pass
        except Exception as e:
            print(f"      ⚠ Claude batch error: {e}")
    improved = sum(1 for o, n in zip(segments_text, all_results) if o != n)
    print(f"      ✓ Claude memperbaiki {improved}/{len(segments_text)} segmen")
    return all_results


def _merge_consecutive_segments(segments: list, gap_threshold: float = 1.5) -> list:
    if not segments: return []
    merged = [segments[0].copy()]
    for seg in segments[1:]:
        prev = merged[-1]
        if seg["start"] - prev["end"] <= gap_threshold and seg.get("text"):
            prev["text"] += " " + seg["text"]; prev["end"] = seg["end"]
        else:
            merged.append(seg.copy())
    return merged


def transcribe_and_diarize(audio_path: str, hf_token: str = "") -> dict:
    """Entry point utama. hf_token diabaikan (kept for API compatibility)."""
    groq_key = GROQ_KEY or os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY tidak ditemukan! Set di file .env")

    wav_path = None
    try:
        print("[1/3] Konversi audio ke WAV 16kHz...")
        wav_path = convert_to_wav(audio_path)
        print("      ✓ Konversi selesai")

        print("[2/3] Transkripsi dengan Groq Whisper large-v3...")
        raw_segs = transcribe_with_groq(wav_path, groq_key)
        if not raw_segs:
            raise ValueError("Groq tidak menghasilkan segmen. Periksa kualitas audio.")

        raw_segs = _merge_consecutive_segments(raw_segs)

        print("[3/3] Merapikan teks...")
        cleaned_texts = [_cleanup_text(s["text"]) for s in raw_segs]
        anthropic_key = ANTHROPIC_KEY or os.getenv("ANTHROPIC_API_KEY", "")
        if anthropic_key and cleaned_texts:
            rapih_texts = _rapikan_dengan_claude_batch(cleaned_texts, anthropic_key)
        else:
            rapih_texts = cleaned_texts

        final_segments = [
            {"start": format_time(s["start"]), "end": format_time(s["end"]),
             "speaker": "Pembicara", "text": text}
            for s, text in zip(raw_segs, rapih_texts)
        ]

        duration = format_time(raw_segs[-1]["end"]) if raw_segs else "00:00"
        print(f"✓ SELESAI — {len(final_segments)} segmen | {duration}")
        return {"segments": final_segments, "speakers": ["Pembicara"],
                "duration": duration, "language": "Bahasa Indonesia"}

    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)