"""
Whisper turbo transkripsiyon.

Kullanım:
    python3 transcribe.py --input audio.wav --language tr --word-timestamps --out transcript.json

İlk çalışmada ~1.5GB turbo modeli indirilir, sonra cache'lenir.
"""
from __future__ import annotations
import argparse, json, time, sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True, help="Input audio file (wav/mp3/m4a)")
    ap.add_argument("--language", type=str, default="tr", help="Language code (tr, en, ...)")
    ap.add_argument("--model", type=str, default="turbo",
                    choices=["tiny", "base", "small", "medium", "large", "turbo"])
    ap.add_argument("--word-timestamps", action="store_true", help="Per-word timestamps (slower, needed for SRT)")
    ap.add_argument("--out", type=Path, required=True, help="Output JSON path")
    ap.add_argument("--also-text", action="store_true", help="Also write a .txt sibling")
    args = ap.parse_args()

    try:
        import whisper
    except ImportError:
        print("❌ openai-whisper not installed. Run: pip install openai-whisper", file=sys.stderr)
        sys.exit(1)

    print(f"Loading model: {args.model}", flush=True)
    t0 = time.time()
    model = whisper.load_model(args.model)
    print(f"  loaded in {time.time()-t0:.1f}s", flush=True)

    print("Transcribing...", flush=True)
    t0 = time.time()
    result = model.transcribe(
        str(args.input),
        language=args.language,
        verbose=False,
        word_timestamps=args.word_timestamps,
        condition_on_previous_text=False,
        temperature=0.0,
    )
    print(f"  done in {time.time()-t0:.1f}s · {len(result['segments'])} segments", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"✅ Wrote {args.out}")

    if args.also_text:
        txt_path = args.out.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for s in result["segments"]:
                f.write(f"[{s['start']:7.2f} -> {s['end']:7.2f}] {s['text'].strip()}\n")
        print(f"✅ Wrote {txt_path}")


if __name__ == "__main__":
    main()
