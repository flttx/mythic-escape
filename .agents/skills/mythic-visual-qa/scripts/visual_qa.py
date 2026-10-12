#!/usr/bin/env python3
"""Visual QA evidence registry and contact sheets. Does not capture Unreal frames."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import struct
import sys

CHAPTERS = ("kraken", "leviathan", "jormungandr", "behemoth", "ziz")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def image_size(path):
    with path.open("rb") as file:
        header = file.read(26)
    if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
        size = struct.unpack(">II", header[16:24])
    else:
        try:
            from PIL import Image
        except ImportError as err:
            raise ValueError("Pillow is needed for non-PNG images") from err
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            size = image.size
    if min(size) < 16 or max(size) > 32768:
        raise ValueError("Invalid image dimensions")
    return list(size)


def record(args):
    capture = Path(args.capture).resolve(strict=True)
    reference = Path(args.reference).resolve(strict=True) if args.reference else None
    output = Path(args.output).resolve()
    if output.exists() and not args.force:
        raise ValueError("Manifest exists. --force required to overwrite.")
    data = {
        "schema": "mythic-visual-qa/1",
        "chapter": args.chapter, "gate": args.gate,
        "origin_claim": args.source,
        "origin_proof": "CLAIM ONLY: verify actual UE capture tool / PIE log separately",
        "capture": str(capture), "sha256": digest(capture),
        "size": image_size(capture),
        "reference": str(reference) if reference else None,
        "reference_sha256": digest(reference) if reference else None,
        "map": args.scene, "phase": args.phase, "camera": args.camera,
        "quality_preset": args.preset, "random_seed": args.seed,
        "hardware": args.hardware, "frame_ms": args.frame_ms,
        "ue_evidence_log": args.ue_log, "notes": args.notes,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "visual_status": "NOT_VERIFIED",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("EVIDENCE_RECORDED="+str(output))
    print("IMAGE_SIZE="+str(data["size"]))
    print("VISUAL_QUALITY=NOT_VERIFIED (requires actual image review)")


def verify(args):
    data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if data.get("schema") != "mythic-visual-qa/1":
        raise ValueError("Unknown evidence schema")
    capture = Path(data["capture"])
    if digest(capture) != data["sha256"] or image_size(capture) != data["size"]:
        raise ValueError("Capture modified since recording")
    if data.get("reference") and digest(Path(data["reference"])) != data["reference_sha256"]:
        raise ValueError("Reference modified since recording")
    print("INTEGRITY=PASS")
    print("ORIGIN_CLAIM="+data["origin_claim"]+" (not independently verified by this script)")
    print("VISUAL_QUALITY=NOT_ASSESSED")


def sheet(args):
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError as err:
        raise ValueError("Pillow required to create contact sheets") from err
    output = Path(args.output).resolve()
    if output.exists() and not args.force:
        raise ValueError("Contact sheet exists. --force required.")
    canvas = Image.new("RGB", (1760, 610), (24, 28, 35))
    for x, source in ((20, args.capture), (900, args.reference)):
        with Image.open(source) as original:
            picture = ImageOps.contain(original.convert("RGB"), (860, 520))
        canvas.paste(picture, (x+(860-picture.width)//2, 55+(520-picture.height)//2))
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 20), "ACTUAL CAPTURE: verify runtime origin", fill="white")
    draw.text((900, 20), "REFERENCE: design target", fill="white")
    draw.text((20, 585), "REVIEW SHEET ONLY; NO AUTOMATED AESTHETIC SCORE", fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    print("CONTACT_SHEET="+str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("record")
    for key in ("capture","output","scene","phase","camera"):
        r.add_argument("--"+key, required=True)
    r.add_argument("--chapter", choices=CHAPTERS, required=True)
    r.add_argument("--gate", choices=list("ABCDE"), required=True)
    r.add_argument("--source", choices=("pie","packaged","editor","movie"), required=True)
    for key in ("reference","preset","seed","hardware","ue-log","notes"):
        r.add_argument("--"+key, default="")
    r.add_argument("--frame-ms", type=float)
    r.add_argument("--force", action="store_true")
    r.set_defaults(callback=record)
    v = sub.add_parser("verify")
    v.add_argument("--manifest", required=True)
    v.set_defaults(callback=verify)
    t = sub.add_parser("sheet")
    for key in ("capture","reference","output"):
        t.add_argument("--"+key, required=True)
    t.add_argument("--force", action="store_true")
    t.set_defaults(callback=sheet)
    args = parser.parse_args()
    try:
        args.callback(args)
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        print("QA_ERROR="+str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
