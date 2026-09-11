"""
One-time, dependency-free (stdlib only) PNG icon generator for the PWA
manifest - a simple lightning-bolt mark on a dark background. Not a runtime
dependency; run once, output committed to apps/web/public/icons/.

    python3 scripts/gen_pwa_icons.py
"""

import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "apps" / "web" / "public" / "icons"

BG = (15, 23, 42)      # slate-900
BOLT = (250, 204, 21)  # amber-400

# Lightning bolt polygon in a 100x100 unit square, scaled per icon size.
BOLT_POLY = [
    (58, 5), (30, 55), (48, 55), (40, 95),
    (72, 42), (53, 42), (62, 5),
]


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def write_png(path: Path, size: int) -> None:
    poly = [(x * size / 100, y * size / 100) for x, y in BOLT_POLY]
    rows = []
    for py in range(size):
        row = bytearray([0])  # filter type 0
        for px in range(size):
            color = BOLT if point_in_polygon(px + 0.5, py + 0.5, poly) else BG
            row.extend(color)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit, RGB truecolor
    idat = zlib.compress(raw, 9)
    png = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (192, 512, 32):
        out = OUT_DIR / f"icon-{size}.png"
        write_png(out, size)
        print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
