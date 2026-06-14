"""
generator.py v4.0
Generate dokumen Lesson Learned Community of Practice (CoP)
Format sesuai dokumen resmi PUSDIKLAT KP 2025.

Struktur dokumen:
  - Kopsurat PUSDIKLAT KP
  - Judul: LESSON LEARNED / COMMUNITY OF PRACTICE(CoP)
  - Sub-judul topik CoP
  - 1. PENDAHULUAN
       1.1 Executive Summary
       1.2 Pernyataan Isu/Masalah
       1.3 Latar Belakang
       1.4 Maksud dan Tujuan
       1.5 Ruang Lingkup
       1.6 Dasar Pembentukan CoP
  - 2. KEGIATAN YANG DILAKSANAKAN
  - 3. HASIL DAN PEMBAHASAN
       3.1 Pre-existing Policies
       3.2 Poin Diskusi
       3.2.1 Alternatif Pemecahan Masalah
       3.2.2 Keuntungan dan Kelemahan
       3.2.3 Pembelajaran Kunci
  - 4. SIMPULAN DAN REKOMENDASI
       4.1 Kesimpulan
       4.2 Rekomendasi
  - Tanda Tangan
"""
import subprocess, os, json, shutil
from datetime import datetime

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo_kemenkeu.png")

# ── Node.js script ─────────────────────────────────────────────────────────────
_DOCX_JS = r"""
const fs   = require('fs');
const {
  Document, Packer, Paragraph, TextRun, ImageRun,
  Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign,
  HeadingLevel, UnderlineType, TabStopType, LeaderType
} = require('docx');

const data       = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const outputPath = process.argv[3];
const logoPath   = process.argv[4];

const logo = fs.existsSync(logoPath) ? fs.readFileSync(logoPath) : null;

const TNR    = 'Arial';
const bS     = { style: BorderStyle.SINGLE, size: 1, color: '000000' };
const bN     = { style: BorderStyle.NONE,   size: 0, color: 'FFFFFF' };
const noB    = { top: bN, bottom: bN, left: bN, right: bN, insideH: bN, insideV: bN };
const allB   = { top: bS, bottom: bS, left: bS, right: bS };

const t  = (text, size, bold, italic, underline) => new TextRun({
  text: text || '', font: TNR, size: size || 22,
  bold: !!bold, italics: !!italic,
  underline: underline ? { type: UnderlineType.SINGLE } : undefined
});
const p  = (children, align, indent, spaceBefore, spaceAfter) => new Paragraph({
  alignment: align || AlignmentType.JUSTIFIED,
  indent:    indent ? { left: indent } : undefined,
  spacing:   { before: spaceBefore || 0, after: spaceAfter || 80, line: 276 },
  children
});
const ep = (space) => new Paragraph({ spacing: { before: 0, after: space || 80 }, children: [t('')] });

function pBold(text, align, indent, size) {
  return p([t(text, size || 22, true)], align || AlignmentType.JUSTIFIED, indent);
}

function pNormal(text, align, indent) {
  return p([t(text, 22)], align || AlignmentType.JUSTIFIED, indent);
}

// Render teks panjang sebagai beberapa paragraf
function pNormalLong(text, align, indent) {
  if (!text || text.trim() === '-' || text.length <= 600) {
    return [p([t(text || '-', 22)], align || AlignmentType.JUSTIFIED, indent)];
  }
  // Pecah di titik kalimat: cari posisi '. ' lalu bagi jadi chunk ~600 karakter
  const parts = [];
  let remaining = text.trim();
  while (remaining.length > 700) {
    let cutAt = -1;
    // Cari '. ' terdekat setelah karakter ke-400
    for (let i = 400; i < Math.min(remaining.length - 1, 750); i++) {
      if (remaining[i] === '.' && remaining[i+1] === ' ') {
        cutAt = i + 1;
        break;
      }
    }
    if (cutAt === -1) cutAt = 700;
    parts.push(remaining.substring(0, cutAt).trim());
    remaining = remaining.substring(cutAt).trim();
  }
  if (remaining) parts.push(remaining);
  if (parts.length === 0) return [p([t(text, 22)], align || AlignmentType.JUSTIFIED, indent)];
  return parts.map(function(part) { return p([t(part, 22)], align || AlignmentType.JUSTIFIED, indent); });
}

// Section heading: "1 PENDAHULUAN" style
function headingSection(num, title) {
  return p([t(num + ' ' + title, 22, true)], AlignmentType.LEFT, undefined, 120, 80);
}

// Sub-heading: "1.1 Executive Summary" style
function headingSub(num, title) {
  return p([t(num + ' ' + title, 22, true)], AlignmentType.LEFT, 360, 80, 60);
}

// Sub-sub heading: "3.2.1 Alternatif Pemecahan Masalah"
function headingSubSub(num, title) {
  return p([t(num + ' ' + title, 22, true)], AlignmentType.LEFT, 720, 60, 40);
}

function tc(content, opts) {
  opts = opts || {};
  const children = typeof content === 'string'
    ? [p([opts.bold ? t(content, opts.size, true) : t(content, opts.size)], opts.align || AlignmentType.LEFT)]
    : content;
  return new TableCell({
    borders:       opts.borders !== undefined ? opts.borders : allB,
    width:         opts.w ? { size: opts.w, type: WidthType.DXA } : undefined,
    verticalAlign: opts.va || VerticalAlign.CENTER,
    margins:       { top: 60, bottom: 60, left: 100, right: 100 },
    children
  });
}

// ── KOPSURAT ─────────────────────────────────────────────────────────────────
const logoCell = new TableCell({
  rowSpan: 3,
  borders: noB,
  width:   { size: 1300, type: WidthType.DXA },
  verticalAlign: VerticalAlign.CENTER,
  margins: { top: 0, bottom: 0, left: 0, right: 100 },
  children: logo
    ? [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new ImageRun({ data: logo, transformation: { width: 78, height: 78 }, type: 'png' })]
      })]
    : [ep()]
});

const kopsurat = new Table({
  width: { size: 9638, type: WidthType.DXA },
  columnWidths: [1300, 8338],
  borders: { top: bN, left: bN, right: bN, insideH: bN, insideV: bN, bottom: { style: BorderStyle.THICK, size: 18, color: '000000' } },
  rows: [
    new TableRow({ children: [
      logoCell,
      tc([p([t('PUSDIKLAT', 22, true)], AlignmentType.CENTER)], { borders: noB, w: 8338 }),
    ]}),
    new TableRow({ children: [
      tc([p([t('KP', 22, true)], AlignmentType.CENTER)], { borders: noB, w: 8338 }),
    ]}),
    new TableRow({ children: [
      tc([p([t('KEMENTERIAN KEUANGAN REPUBLIK INDONESIA', 18)], AlignmentType.CENTER)], { borders: noB, w: 8338 }),
    ]}),
  ]
});

// ── DAFTAR ISI (teks dengan dot leader, tanpa tabel) ────────────────────────
// Tab stop: dot leader di posisi 8500 twips (hampir penuh halaman), nomor hal di kanan
// TabStopType and LeaderType are already imported via the main require('docx') above

function makeDaftarIsiLine(no, judul, hal, isBab, indentLevel) {
  // indent: level 0 = bab utama, level 1 = sub-bab (360 twips), level 2 = sub-sub-bab (720 twips)
  const indentLeft = indentLevel === 2 ? 720 : indentLevel === 1 ? 360 : 0;
  const label = no ? no + '  ' + judul : judul;
  return new Paragraph({
    indent: indentLeft ? { left: indentLeft } : undefined,
    spacing: { before: isBab ? 80 : 40, after: 40, line: 276 },
    tabStops: [
      { type: TabStopType.RIGHT, position: 8500, leader: LeaderType.DOT }
    ],
    children: [
      new TextRun({
        text: label,
        font: 'Arial',
        size: 22,
        bold: isBab,
      }),
      new TextRun({
        text: '\t' + (hal || ''),
        font: 'Arial',
        size: 22,
        bold: isBab,
      }),
    ]
  });
}

const daftarIsiLines = (data.daftar_isi || []).map((row) => {
  const indentLevel = row.indent || 0;
  return makeDaftarIsiLine(row.no || '', row.judul || '', row.hal || '', row.is_bab && !indentLevel, indentLevel);
});

// ── PEMBAHASAN SEGMEN (transkripsi diskusi) ──────────────────────────────────
const diskusiItems = [];
(data.segmen_diskusi || []).forEach((seg, i) => {
  diskusiItems.push(
    p([t('[' + seg.start + '] ', 20), t(seg.text || '', 22)],
      AlignmentType.JUSTIFIED, 720, 0, 60)
  );
});

// ── SIMPULAN LIST ────────────────────────────────────────────────────────────
const simpulanItems = (data.simpulan || []).map((s, i) =>
  p([t((i+1) + '. ' + s)], AlignmentType.JUSTIFIED, 720)
);

// ── REKOMENDASI LIST ─────────────────────────────────────────────────────────
const rekomendasiItems = (data.rekomendasi_list || []).map((r, i) =>
  p([t((i+1) + ' ' + r)], AlignmentType.JUSTIFIED, 720)
);

// ── TANDA TANGAN TABLE ────────────────────────────────────────────────────────
const ttdTable = new Table({
  width: { size: 9638, type: WidthType.DXA },
  columnWidths: [4819, 4819],
  borders: noB,
  rows: [
    new TableRow({ children: [
      tc([p([t('Jakarta, ' + (data.tanggal || ''))])], { borders: noB, w: 4819 }),
      tc([ep()], { borders: noB, w: 4819 }),
    ]}),
    new TableRow({ children: [
      tc([p([t('Kepala Pusat Pendidikan Dan Pelatihan')]),
          p([t('Keuangan Publik')]),
          p([t('Keuangan,')])], { borders: noB, w: 4819 }),
      tc([ep()], { borders: noB, w: 4819 }),
    ]}),
    new TableRow({ children: [
      tc([new Paragraph({
          spacing: { before: 900, after: 0 },
          children: [t(data.pejabat || '................................', 22, true)]
        })], { borders: noB, w: 4819 }),
      tc([ep()], { borders: noB, w: 4819 }),
    ]}),
  ]
});

// ── DOCUMENT ──────────────────────────────────────────────────────────────────
const doc = new Document({
  styles: { default: { document: { run: { font: 'Arial', size: 22 } } } },
  sections: [{
    properties: {
      page: {
        size:   { width: 11906, height: 16838 },  // A4
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1800 }
      }
    },
    children: [
      // Kopsurat
      kopsurat,
      new Paragraph({
        spacing: { before: 40, after: 120 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000' } },
        children: [t('')]
      }),

      // Judul
      p([t('LESSON LEARNED', 28, true)], AlignmentType.CENTER),
      p([t('COMMUNITY OF PRACTICE(CoP)', 24, true, true)], AlignmentType.CENTER),
      ep(),
      p([t(data.judul_cop || '', 22, true)], AlignmentType.CENTER),
      ep(),
      ep(),

      // Daftar Isi
      pBold('DAFTAR ISI', AlignmentType.CENTER),
      ep(),
      ...daftarIsiLines,
      ep(), ep(),

      // 1. PENDAHULUAN
      headingSection('1', 'PENDAHULUAN'),
      headingSub('1.1', 'Executive Summary'),
      ...pNormalLong(data.executive_summary || '-', AlignmentType.JUSTIFIED, 720),
      ep(),

      headingSub('1.2', 'Pernyataan Isu/Masalah'),
      ...pNormalLong(data.isu_masalah || '-', AlignmentType.JUSTIFIED, 720),
      ep(),

      headingSub('1.3', 'Latar Belakang'),
      ...pNormalLong(data.latar_belakang || '-', AlignmentType.JUSTIFIED, 720),
      ep(),

      headingSub('1.4', 'Maksud dan Tujuan'),
      ...pNormalLong(data.maksud_tujuan || '-', AlignmentType.JUSTIFIED, 720),
      ep(),

      headingSub('1.5', 'Ruang Lingkup'),
      ...pNormalLong(data.ruang_lingkup || '-', AlignmentType.JUSTIFIED, 720),
      ep(),

      headingSub('1.6', 'Dasar Pembentukan CoP'),
      ...pNormalLong(data.dasar_cop || '-', AlignmentType.JUSTIFIED, 720),
      ep(), ep(),

      // 2. KEGIATAN
      headingSection('2', 'KEGIATAN YANG DILAKSANAKAN'),
      ...pNormalLong(data.kegiatan || '-', AlignmentType.JUSTIFIED, 720),
      ep(), ep(),

      // 3. HASIL DAN PEMBAHASAN
      headingSection('3', 'HASIL DAN PEMBAHASAN'),
      headingSub('3.1', 'Pre-existing Policies'),
      ...pNormalLong(data.preexisting_policies || '-', AlignmentType.JUSTIFIED, 720),
      ep(),

      headingSub('3.2', 'Poin Diskusi'),
      ep(),

      headingSubSub('3.2.1', 'Alternatif Pemecahan Masalah'),
      ...pNormalLong(data.alternatif_masalah || '-', AlignmentType.JUSTIFIED, 1080),
      ep(),

      headingSubSub('3.2.2', 'Keuntungan dan Kelemahan'),
      ...pNormalLong(data.keuntungan_kelemahan || '-', AlignmentType.JUSTIFIED, 1080),
      ep(),

      headingSubSub('3.2.3', 'Pembelajaran Kunci'),
      ep(),
      ...diskusiItems,
      ep(), ep(),

      // 4. SIMPULAN DAN REKOMENDASI
      headingSection('4', 'SIMPULAN DAN REKOMENDASI'),
      headingSub('4.1', 'Kesimpulan'),
      ...simpulanItems,
      ep(),

      headingSub('4.2', 'Rekomendasi'),
      ...rekomendasiItems,
      ep(), ep(),

      // Tanda Tangan
      ttdTable,
      ep(),
    ]
  }]
});

Packer.toBuffer(doc)
  .then(buf => { fs.writeFileSync(outputPath, buf); console.log('OK'); })
  .catch(err => { console.error('ERROR:' + err.message); process.exit(1); });
"""


def _ensure_docx_module():
    node_modules_path = os.path.join(BASE_DIR, "node_modules", "docx")
    if not os.path.isdir(node_modules_path):
        print("⚙ node_modules/docx tidak ditemukan — menjalankan npm install...")
        # Di Windows, npm bisa bernama npm.cmd
        npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm_cmd:
            raise RuntimeError(
                "npm tidak ditemukan! Pastikan Node.js sudah terinstall dan ada di PATH.\n"
                "Download: https://nodejs.org/"
            )
        # Di Windows pakai shell=True dengan string command agar npm.cmd berjalan
        if os.name == "nt":
            result = subprocess.run(
                f'"{npm_cmd}" install docx',
                capture_output=True, text=True, cwd=BASE_DIR, timeout=180, shell=True
            )
        else:
            result = subprocess.run(
                [npm_cmd, "install", "docx"],
                capture_output=True, text=True, cwd=BASE_DIR, timeout=180
            )
        if result.returncode != 0:
            raise RuntimeError(
                f"npm install docx gagal:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}\n\n"
                "Jalankan manual: cd ke folder CoP-AI, lalu ketik: npm install docx"
            )
        print("✓ npm install docx selesai")
    # Pastikan node juga tersedia
    node_cmd = shutil.which("node") or shutil.which("node.exe")
    if not node_cmd:
        raise RuntimeError(
            "node tidak ditemukan! Pastikan Node.js sudah terinstall dan ada di PATH.\n"
            "Download: https://nodejs.org/"
        )


def _parse_rekomendasi_text(text: str) -> list:
    """Parse teks rekomendasi AI menjadi list poin."""
    if not text or not text.strip():
        return ["(diisi setelah diskusi)"]
    import re
    lines   = [l.strip() for l in text.strip().split("\n") if l.strip()]
    cleaned = []
    for l in lines:
        l = re.sub(r'^\d+\.\s*', '', l)
        if l:
            cleaned.append(l)
    return cleaned if cleaned else ["(diisi setelah diskusi)"]


def _build_daftar_isi(peserta_list: list) -> list:
    """
    Build daftar isi dari peserta_list (format frontend: {nama, jabatan, instansi}).
    Frontend mengirim daftar isi sebagai daftar bab+subbab.
    """
    daftar = []
    for row in peserta_list:
        nama    = row.get("nama", "")
        jabatan = row.get("jabatan", "")
        # nama bisa berupa "1. Pendahuluan" atau "1.1 Executive Summary" dst
        is_bab  = bool(nama and "." in nama and len(nama.split(".")[0]) <= 2)
        indent  = 1 if (nama and nama[0].isdigit() and "." in nama and
                        len(nama.split(".")[0]) <= 2 and nama.count(".") > 1) else 0
        daftar.append({
            "no":     nama.split(" ")[0] if nama else str(len(daftar)+1),
            "judul":  " ".join(nama.split(" ")[1:]) if nama and " " in nama else nama,
            "hal":    jabatan,
            "is_bab": not bool(indent),
            "indent": indent,
        })
    return daftar


def _extract_segmen_for_pembahasan(segments: list) -> list:
    """Ambil segmen untuk bagian Pembelajaran Kunci (3.2.3)."""
    return [{"start": s.get("start", ""), "text": s.get("text", "")} for s in segments]


def _build_payload(data: dict) -> dict:
    segments      = data.get("segments", [])
    peserta_list  = data.get("peserta_list", [])
    tanggal       = data.get("tanggal", datetime.now().strftime("%d %B %Y"))
    judul_cop     = data.get("judul_cop", "") or data.get("perihal", "COMMUNITY OF PRACTICE")
    isu_masalah   = data.get("isu_masalah", "") or data.get("agenda_text", "")
    nomor_sk      = data.get("nomor_sk", "")

    # Ambil hasil analisis AI (dict dari generate_analisis_cop)
    ai = data.get("analisis_ai") or {}

    # Daftar isi dari peserta_list
    daftar_isi = _build_daftar_isi(peserta_list)

    # full_text untuk fallback jika AI tidak tersedia
    full_text = " ".join([s.get("text", "") for s in segments if s.get("text")])

    # ── Helper: ambil dari AI atau fallback ke default ──────────────────────────
    def ai_or(key, fallback):
        val = ai.get(key, "")
        return val.strip() if isinstance(val, str) and val.strip() else fallback

    def ai_list(key, fallback_list):
        val = ai.get(key, [])
        return val if isinstance(val, list) and val else fallback_list

    # ── Konten bab dari AI atau fallback ───────────────────────────────────────
    exec_summary = ai_or("executive_summary", _extract_exec_summary(full_text, judul_cop))

    isu_final = ai_or("isu_masalah",
        isu_masalah or "(Isu/masalah tidak tersedia — AI tidak menghasilkan analisis untuk rekaman ini.)")

    latar_belakang = ai_or("latar_belakang",
        "(Latar belakang tidak tersedia — pastikan API key AI sudah diisi di .env)")

    maksud_tujuan = ai_or("maksud_tujuan",
        "(Maksud dan tujuan tidak tersedia — pastikan API key AI sudah diisi di .env)")

    ruang_lingkup = ai_or("ruang_lingkup",
        "(Ruang lingkup tidak tersedia — pastikan API key AI sudah diisi di .env)")

    preexisting = ai_or("preexisting_policies",
        "(Kebijakan terkait tidak tersedia — pastikan API key AI sudah diisi di .env)")

    alternatif = ai_or("alternatif_masalah", _extract_alternatif(full_text))

    keuntungan = ai_or("keuntungan_kelemahan",
        "(Analisis keuntungan dan kelemahan tidak tersedia — pastikan API key AI sudah diisi di .env)")

    # Pembelajaran kunci: dari AI (list poin) atau fallback ke segmen transkripsi
    pembelajaran_ai = ai_list("pembelajaran_kunci", [])
    if pembelajaran_ai:
        # Ubah list poin AI menjadi segmen format yang dipakai JS
        segmen_diskusi = [{"start": "", "text": poin} for poin in pembelajaran_ai]
    else:
        segmen_diskusi = _extract_segmen_for_pembahasan(segments)

    rek_list  = ai_list("rekomendasi",
        _parse_rekomendasi_text(data.get("rekomendasi", "") or data.get("kesimpulan", "")))
    simpulan  = ai_list("simpulan",
        rek_list[:3] if rek_list and rek_list[0] != "(diisi setelah diskusi)" else
        ["(diisi setelah diskusi)", "(diisi setelah diskusi)", "(diisi setelah diskusi)"])

    return {
        "judul_cop":            judul_cop,
        "tanggal":              tanggal,
        "hari":                 data.get("hari", ""),
        "jam":                  data.get("jam", ""),
        "tempat":               data.get("tempat", ""),
        "pejabat":              data.get("pejabat", "................................"),
        "notulis":              data.get("notulis", "................................"),
        "jabatan_pejabat":      data.get("jabatan_pejabat", ""),
        "nomor_sk":             nomor_sk,
        "daftar_isi":           daftar_isi,
        "executive_summary":    exec_summary,
        "isu_masalah":          isu_final,
        "latar_belakang":       latar_belakang,
        "maksud_tujuan":        maksud_tujuan,
        "ruang_lingkup":        ruang_lingkup,
        "dasar_cop":            nomor_sk or "(diisi sesuai Surat Keputusan penyelenggaraan CoP)",
        "kegiatan":             ai_or("kegiatan", "(informasi kegiatan tidak tersedia dalam rekaman)"),
        "preexisting_policies": preexisting,
        "alternatif_masalah":   alternatif,
        "keuntungan_kelemahan": keuntungan,
        "segmen_diskusi":       segmen_diskusi,
        "simpulan":             simpulan,
        "rekomendasi_list":     rek_list,
    }


def _extract_exec_summary(full_text: str, judul: str) -> str:
    if not full_text or len(full_text) < 100:
        return f"(Executive summary tidak tersedia untuk: {judul})"
    # Ambil ~500 karakter pertama dan jadikan summary
    preview = full_text[:600].strip()
    if len(full_text) > 600:
        preview = preview[:preview.rfind(" ")] + "..."
    return preview


def _extract_alternatif(full_text: str) -> str:
    if not full_text or len(full_text) < 50:
        return "Terdapat beberapa alternatif pemecahan masalah yang dibahas dalam forum CoP ini."
    mid = len(full_text) // 3
    chunk = full_text[mid:mid + 500].strip()
    if len(full_text[mid:]) > 500:
        chunk = chunk[:chunk.rfind(" ")] + "..."
    return chunk


def generate_docx(data: dict, output_path: str):
    _ensure_docx_module()
    payload = _build_payload(data)

    script_path = os.path.join(BASE_DIR, "_cop_gen_tmp.js")
    json_path   = os.path.join(BASE_DIR, "_cop_data_tmp.json")

    try:
        with open(script_path, mode='w', encoding='utf-8') as sf:
            sf.write(_DOCX_JS)
        with open(json_path, mode='w', encoding='utf-8') as jf:
            json.dump(payload, jf, ensure_ascii=False, indent=2)

        node_cmd = shutil.which("node") or shutil.which("node.exe") or "node"
        result = subprocess.run(
            [node_cmd, script_path, json_path, output_path, LOGO_PATH],
            capture_output=True, text=True, timeout=90, cwd=BASE_DIR
        )
        if result.returncode != 0:
            raise RuntimeError(f"Node.js gagal:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        print(f"✓ DOCX disimpan: {output_path}")

    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)
        if os.path.exists(json_path):
            os.unlink(json_path)


def generate_pdf(docx_path: str, output_dir: str) -> str | None:
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
            check=True, capture_output=True, timeout=120
        )
        pdf_path = os.path.join(output_dir, os.path.basename(docx_path).replace(".docx", ".pdf"))
        if os.path.exists(pdf_path):
            print(f"✓ PDF disimpan: {pdf_path}")
            return pdf_path
        return None
    except Exception as e:
        print(f"⚠ PDF generation gagal: {e}")
        return None