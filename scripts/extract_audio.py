"""
Timeline-doğru ses çıkarma (CapCut farkındalı).

İki mod:
  1. CapCut timeline'ından: tüm video track'lerin segment'lerini timeline pozisyonlarına yerleştir,
     vol=0 muted segment'leri ATLA, ufak gap'leri silence ile doldur.
  2. Düz dosyadan: video.mov → audio.wav (16kHz mono).

CapCut modu önemli çünkü:
  - Multi-track overlay'ler (B-roll) timeline-doğru mix edilir
  - Muted segment'ler dahil edilmezse SRT timing'i CapCut timeline'ı ile birebir eşleşir

CLI kullanımı:
    # Timeline'dan
    python3 extract_audio.py \
        --capcut-project ~/Movies/CapCut/.../0425 \
        --timeline "Timeline 03" \
        --out /tmp/audio.wav

    # Düz dosyadan
    python3 extract_audio.py --input video.mov --out /tmp/audio.wav
"""
from __future__ import annotations
import argparse, os, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

# Project-local imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capcut_parser import load_timeline_segments, find_timeline, list_projects, CAPCUT_ROOT_DEFAULT  # noqa

SR = 16000


def extract_segment_wav(src_path: str, src_start: float, src_dur: float, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{src_start:.3f}",
        "-i", src_path,
        "-t", f"{src_dur:.3f}",
        "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_f32le",
        out_path,
    ]
    subprocess.run(cmd, check=True)


def extract_from_timeline(project_dir: Path, timeline_name: str, out_wav: Path) -> float:
    """Returns total timeline duration in seconds."""
    tl_dir = find_timeline(project_dir, timeline_name)
    if not tl_dir:
        raise SystemExit(f"❌ Timeline not found: {timeline_name}")

    segs = [s for s in load_timeline_segments(tl_dir)
            if not s.is_image and not s.is_muted and os.path.exists(s.src_path)]
    if not segs:
        raise SystemExit("❌ No audio-bearing segments found")

    total_s = max(s.tl_start + s.tl_duration for s in segs)
    total_samples = int(round(total_s * SR)) + SR  # 1s padding
    mix = np.zeros(total_samples, dtype=np.float32)

    print(f"Mixing {len(segs)} segments → {total_s:.2f}s ({total_s/60:.2f} min)", flush=True)

    with tempfile.TemporaryDirectory(prefix="vidkit_") as tmp:
        for i, s in enumerate(segs):
            chunk_path = os.path.join(tmp, f"{i:04d}.wav")
            extract_segment_wav(s.src_path, s.src_start, s.src_duration, chunk_path)
            wav, _ = sf.read(chunk_path, dtype="float32")
            start = int(round(s.tl_start * SR))
            end = min(start + len(wav), total_samples)
            mix[start:end] += wav[:end - start]
            if i % 30 == 0:
                print(f"  ...{i+1}/{len(segs)}", flush=True)

    # Normalize to avoid clipping
    peak = float(np.max(np.abs(mix)))
    if peak > 0.95:
        mix *= (0.95 / peak)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), mix, SR, subtype="PCM_16")
    return total_s


def extract_from_file(input_path: Path, out_wav: Path) -> float:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(input_path),
        "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True)
    # probe duration
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out_wav)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, help="Direct video/audio file (alternatif: --capcut-project)")
    ap.add_argument("--capcut-project", type=Path, help="Path to CapCut project dir (e.g. .../0425)")
    ap.add_argument("--timeline", type=str, help="Timeline name (with --capcut-project)")
    ap.add_argument("--out", type=Path, required=True, help="Output WAV path")
    args = ap.parse_args()

    if args.capcut_project and args.timeline:
        dur = extract_from_timeline(args.capcut_project, args.timeline, args.out)
    elif args.input:
        dur = extract_from_file(args.input, args.out)
    else:
        ap.error("Either --input OR (--capcut-project + --timeline) required")

    print(f"✅ Wrote {args.out} — {dur:.2f}s")


if __name__ == "__main__":
    main()
