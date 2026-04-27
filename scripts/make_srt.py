"""
Word-level Whisper transkriptinden temiz SRT alt yazı üretir.

Özellikler:
- Cümleleri ≤max-duration sn / ≤max-chars char chunk'lara böler
- Türkçe AI/dev sözlük düzeltmesi (Cloud→Claude, Versal→Vercel, vb.)
- Whisper "MCP 'ler" gibi apostrof boşluk hatasını temizler
- 2-satır chunk için sözcük sınırına bakarak kırar

CLI:
    python3 make_srt.py --input transcript.json --out altyazi.srt
    python3 make_srt.py --input transcript.json --out altyazi.srt --add-fix "X kod" "Xcode"
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path


# -------- Sözlük (genişletilebilir) --------
DEFAULT_FIXES = [
    # Konuşmacı (kullanıcılar kendi adlarına özelleştirsin)
    (r"\bSermen Kocabi\b", "Selma Kocabıyık"),
    (r"\bSermen\b", "Selma"),

    # Claude / Cloud confusion
    (r"\bCloud kodumun\b", "Claude Code'umun"),
    (r"\bCloud kodumu\b", "Claude Code'umu"),
    (r"\bCloud kodum\b", "Claude Code'um"),
    (r"\bCloud kodunun\b", "Claude Code'un"),
    (r"\bCloud kodun\b", "Claude Code'un"),
    (r"\bCloud kodu\b", "Claude Code'u"),
    (r"\bCloud kod\b", "Claude Code"),
    (r"\bCloud Code\b", "Claude Code"),
    (r"\bCloud'a\b", "Claude'a"),
    (r"\bCloud'un\b", "Claude'un"),
    (r"\bCloud'umun\b", "Claude'umun"),
    (r"\bCloud\b", "Claude"),

    # Tool/marka isimleri
    (r"\bMobe AI\b", "mob.ai"),
    (r"\bMobe Ai\b", "mob.ai"),
    (r"\bMobe ai\b", "mob.ai"),
    (r"\bMob AI\b", "mob.ai"),
    (r"\bN8N\b", "n8n"),
    (r"\bN8'in\b", "n8n"),
    (r"\bN8\b", "n8n"),
    (r"\bVersal\b", "Vercel"),
    (r"\bX kodumun\b", "Xcode'umun"),
    (r"\bX kodumu\b", "Xcode'umu"),
    (r"\bX kodum\b", "Xcode'um"),
    (r"\bX kodun\b", "Xcode'un"),
    (r"\bX kodu\b", "Xcode'u"),
    (r"\bX kod\b", "Xcode"),
    (r"\bAntropik\b", "Anthropic"),
    (r"\bTropic\b", "Anthropic"),
    (r"\bMTP\b", "MCP"),
    (r"\bMcP\b", "MCP"),
    (r"\bGmate\b", "Gmail"),
    (r"\bgmate\b", "Gmail"),

    # Türkçe yazım
    (r"\b[Ss]am olarak\b", "Tam olarak"),
    (r"\byapay zekam\b", "yapay zeka"),
    (r"\byapay zekareleri\b", "yapay zeka videoları"),
    (r"\bvazgeçilmesi olmazsa olmazı\b", "olmazsa olmazı"),
    (r"\bmaniyel\b", "manuel"),
    (r"\bbalantıyı\b", "bağlantıyı"),
    (r"\balayızı\b", "arayüzü"),
    (r"\balayüzü\b", "arayüzü"),
    (r"\bhoşgeldiniz\b", "hoş geldiniz"),

    # Server suffixes
    (r"\bservera\b", "server'a"),
    (r"\bserverda\b", "server'da"),
    (r"\bserverdan\b", "server'dan"),
    (r"\bserverlara\b", "server'lara"),
    (r"\bserverleri\b", "server'ları"),

    # Whisper word-tokenizer artifacts (apostrof öncesi boşluk)
    (r"\s+'", "'"),
    (r"\s+,", ","),
    (r"\s+\.", "."),
    (r"\s+\?", "?"),
    (r"\s+!", "!"),
    (r"\s+", " "),
]


def srt_time(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int(round((s - int(s)) * 1000))
    if ms == 1000:
        ms = 0
        sec += 1
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def apply_fixes(text: str, fixes: list[tuple[str, str]]) -> str:
    out = text.strip()
    for pat, rep in fixes:
        out = re.sub(pat, rep, out)
    return out.strip()


def split_two_lines(text: str, max_line_chars: int = 42) -> str:
    if len(text) <= max_line_chars:
        return text
    words = text.split()
    half = len(text) // 2
    cum = 0
    cut = len(words) // 2
    for i, w in enumerate(words):
        cum += len(w) + 1
        if cum >= half:
            cut = i + 1
            break
    return " ".join(words[:cut]) + "\n" + " ".join(words[cut:])


def chunk_words(words: list[dict], max_dur: float, max_chars: int) -> list[dict]:
    chunks: list[dict] = []
    cur = {"start": None, "end": None, "text": ""}
    for w in words:
        token = w["word"].strip() if "word" in w else w.get("w", "").strip()
        if not token:
            continue
        if cur["start"] is None:
            cur = {"start": w["start"], "end": w["end"], "text": token}
            continue
        new_text = (cur["text"] + " " + token).strip()
        new_dur = w["end"] - cur["start"]
        if new_dur > max_dur or len(new_text) > max_chars:
            chunks.append(cur)
            cur = {"start": w["start"], "end": w["end"], "text": token}
        else:
            cur["text"] = new_text
            cur["end"] = w["end"]
            if token.endswith((".", "!", "?")) and len(new_text) >= 30:
                chunks.append(cur)
                cur = {"start": None, "end": None, "text": ""}
    if cur["start"] is not None:
        chunks.append(cur)
    return chunks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True, help="Whisper transcript.json (word_timestamps=True ile üretilmiş)")
    ap.add_argument("--out", type=Path, required=True, help="Output .srt path")
    ap.add_argument("--max-duration", type=float, default=3.5, help="Maks chunk süresi (sn)")
    ap.add_argument("--max-chars", type=int, default=80, help="Maks chunk karakter sayısı")
    ap.add_argument("--max-line-chars", type=int, default=42, help="Satır başına maks karakter")
    ap.add_argument("--add-fix", nargs=2, action="append", metavar=("PATTERN", "REPLACEMENT"),
                    help="Ek regex sözlük girdisi (birden fazla verilebilir)")
    ap.add_argument("--no-default-fixes", action="store_true", help="Varsayılan sözlüğü devre dışı bırak")
    args = ap.parse_args()

    data = json.loads(args.input.read_text())
    words: list[dict] = []
    for seg in data.get("segments", []):
        words.extend(seg.get("words", []))

    if not words:
        print("❌ No word-level timestamps found. Run transcribe.py with --word-timestamps", file=sys.stderr)
        sys.exit(1)

    chunks = chunk_words(words, args.max_duration, args.max_chars)

    fixes = [] if args.no_default_fixes else list(DEFAULT_FIXES)
    if args.add_fix:
        # User fixes go FIRST so they override generic ones
        fixes = [(p, r) for p, r in args.add_fix] + fixes

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for i, c in enumerate(chunks, start=1):
            text = apply_fixes(c["text"], fixes)
            if not text:
                continue
            text = split_two_lines(text, args.max_line_chars)
            f.write(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{text}\n\n")

    avg = sum(c["end"] - c["start"] for c in chunks) / max(len(chunks), 1)
    print(f"✅ Wrote {args.out}")
    print(f"   {len(chunks)} chunks · avg {avg:.2f}s/chunk")


if __name__ == "__main__":
    main()
