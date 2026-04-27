"""
CapCut Mac draft_info.json parser.

CapCut Mac, projelerini şu formatta saklar:
~/Movies/CapCut/User Data/Projects/com.lveditor.draft/<project_name>/
├── draft_info.json         (ana proje dosyası)
└── Timelines/
    └── <timeline_uuid>/
        └── draft_info.json (her timeline ayrı)

Bu modül:
- Hangi projelerin/timeline'ların olduğunu listeler
- Bir timeline'ın segment'lerini parse eder (timeline_start, source_start, duration, volume, path)
- Multi-track aware (Track 0+1+2+...) — her track'i ayrı verir
- vol=0 muted segment'leri işaretler

CLI kullanımı:
    python3 capcut_parser.py --list
    python3 capcut_parser.py --project 0425 --timeline "Timeline 03"
"""
from __future__ import annotations
import argparse, json, sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator

CAPCUT_ROOT_DEFAULT = Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"


@dataclass
class Segment:
    track_index: int
    tl_start: float        # timeline'da başlangıç (saniye)
    tl_duration: float
    src_start: float       # source dosyada başlangıç (saniye)
    src_duration: float
    src_path: str
    src_name: str
    volume: float
    is_muted: bool
    is_image: bool


def list_projects(root: Path = CAPCUT_ROOT_DEFAULT) -> list[Path]:
    if not root.exists():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.')])


def list_timelines(project_dir: Path) -> list[dict]:
    timelines_dir = project_dir / "Timelines"
    project_json = timelines_dir / "project.json"
    if not project_json.exists():
        return []
    data = json.loads(project_json.read_text())
    return [{"id": t["id"], "name": t["name"]} for t in data.get("timelines", [])
            if not t.get("is_marked_delete")]


def load_timeline_segments(timeline_dir: Path) -> Iterator[Segment]:
    """draft_info.json'dan tüm video track'lerin segment'lerini yield eder."""
    draft_path = timeline_dir / "draft_info.json"
    if not draft_path.exists():
        raise FileNotFoundError(f"draft_info.json not found in {timeline_dir}")

    data = json.loads(draft_path.read_text())
    vid_map = {v["id"]: v for v in data.get("materials", {}).get("videos", [])}

    for ti, track in enumerate(data.get("tracks", [])):
        if track.get("type") != "video":
            continue
        for s in track.get("segments", []):
            mat = vid_map.get(s.get("material_id"), {})
            path = mat.get("path") or ""
            name = mat.get("material_name") or ""
            tl = s.get("target_timerange", {})
            sr = s.get("source_timerange", {})
            vol = s.get("volume", 1.0)
            yield Segment(
                track_index=ti,
                tl_start=tl.get("start", 0) / 1_000_000,
                tl_duration=tl.get("duration", 0) / 1_000_000,
                src_start=sr.get("start", 0) / 1_000_000,
                src_duration=sr.get("duration", 0) / 1_000_000,
                src_path=path,
                src_name=name,
                volume=float(vol),
                is_muted=(vol == 0),
                is_image=path.lower().endswith((".png", ".jpg", ".jpeg")),
            )


def find_timeline(project_dir: Path, timeline_name: str) -> Path | None:
    for tl in list_timelines(project_dir):
        if tl["name"].strip().lower() == timeline_name.strip().lower():
            return project_dir / "Timelines" / tl["id"]
    return None


# ----- CLI -----
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=CAPCUT_ROOT_DEFAULT,
                    help="CapCut projects root (default: ~/Movies/CapCut/.../com.lveditor.draft)")
    ap.add_argument("--list", action="store_true", help="List all projects + their timelines")
    ap.add_argument("--project", type=str, help="Project folder name (e.g. '0425')")
    ap.add_argument("--timeline", type=str, help="Timeline name (e.g. 'Timeline 03')")
    ap.add_argument("--json", action="store_true", help="Output segments as JSON")
    args = ap.parse_args()

    if args.list or not args.project:
        for proj in list_projects(args.root):
            print(f"📁 {proj.name}")
            for tl in list_timelines(proj):
                print(f"    └─ {tl['name']}  ({tl['id'][:8]}…)")
        return

    project_dir = args.root / args.project
    if not project_dir.exists():
        print(f"❌ Project not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.timeline:
        print(f"📁 {args.project}")
        for tl in list_timelines(project_dir):
            print(f"    └─ {tl['name']}")
        return

    tl_dir = find_timeline(project_dir, args.timeline)
    if not tl_dir:
        print(f"❌ Timeline not found: {args.timeline}", file=sys.stderr)
        sys.exit(1)

    segs = list(load_timeline_segments(tl_dir))
    if args.json:
        print(json.dumps([asdict(s) for s in segs], indent=2, ensure_ascii=False))
        return

    audio_segs = [s for s in segs if not s.is_image]
    muted = sum(1 for s in audio_segs if s.is_muted)
    total = max((s.tl_start + s.tl_duration) for s in segs)
    print(f"Timeline: {args.timeline}")
    print(f"  Total segments: {len(segs)}  (audio: {len(audio_segs)}, muted: {muted}, images: {len(segs)-len(audio_segs)})")
    print(f"  Total duration: {total:.2f}s  ({total/60:.2f} min)")
    print()
    sources = sorted({s.src_name for s in segs if s.src_name})
    print(f"  Unique sources ({len(sources)}):")
    for src in sources:
        print(f"    - {src}")


if __name__ == "__main__":
    main()
