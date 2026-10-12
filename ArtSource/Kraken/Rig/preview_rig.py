"""Orthographic part-label + skeleton preview of the derived Kraken rig (numpy/PIL only).

Optional --pose NPZ (frame-major joint positions, from animate_kraken.py) previews deformed
vertices via linear blend skinning, matching the runtime skinning model.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kraken_mesh_io as kio  # noqa: E402

COLOURS = np.array([[200, 200, 200], [230, 80, 80], [80, 200, 90], [80, 120, 240], [240, 200, 60],
                    [200, 90, 220], [70, 220, 220], [250, 140, 40], [150, 110, 70]], np.uint8)
VIEWS = {'top': (0, 1), 'front': (1, 2), 'side': (0, 2)}


def render(points, colours, joints, parents, axes, size=700, lo=None, hi=None, water=None):
    a, b = axes
    lo = np.array([-560.0, -560.0, -40.0]) if lo is None else lo
    hi = np.array([560.0, 560.0, 680.0]) if hi is None else hi
    span = max(hi[a] - lo[a], hi[b] - lo[b])
    sc = (size - 1) / span

    def px(q):
        return (q[..., a] - lo[a]) * sc, size - 1 - (q[..., b] - lo[b]) * sc
    img = np.zeros((size, size, 3), np.uint8) + 18
    depth = np.full((size, size), -np.inf)
    other = 3 - a - b
    x, y = px(points)
    ok = (x >= 0) & (x < size) & (y >= 0) & (y < size)
    xi, yi, d = x[ok].astype(int), y[ok].astype(int), points[ok, other] * (1 if other == 2 else -1)
    order = np.argsort(d)
    img[yi[order], xi[order]] = colours[ok][order]
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    if water is not None and b == 2:
        wy = size - 1 - (water - lo[2]) * sc
        dr.line([(0, wy), (size, wy)], fill=(40, 90, 160), width=1)
    jx, jy = px(joints)
    for i, par in enumerate(parents):
        if par >= 0:
            dr.line([(jx[par], jy[par]), (jx[i], jy[i])], fill=(255, 255, 255), width=2)
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--pose', help='NPZ with skin matrices per frame (animate_kraken output)')
    ap.add_argument('--clip', help='clip name prefix inside the pose NPZ, e.g. Kraken_StrikeA')
    ap.add_argument('--frames', default='0', help='comma separated frame indices for --pose')
    ap.add_argument('--water', type=float, default=280.0)
    args = ap.parse_args()
    p, _ = kio.load()
    rig = np.load(kio.CACHE / 'rig.npz')
    label = rig['label']
    colours = COLOURS[np.clip(label, -1, 8) + 0]
    colours[label == -1] = [255, 255, 255]
    heads, tails, parents = rig['heads'], rig['tails'], rig['parents']
    rows = []
    frames = [int(f) for f in args.frames.split(',')]
    pose = np.load(args.pose) if args.pose else None
    for f in frames:
        if pose is None:
            pts, jts = p, heads
        else:
            skin = pose[args.clip + '__skin'][f]  # (bones, 3, 4) rest->posed affine
            bi, bw = rig['bone_index'], rig['bone_weight']
            pts = np.zeros_like(p, dtype=np.float64)
            ph = np.concatenate([p, np.ones((len(p), 1))], 1)
            for k in range(bi.shape[1]):
                m = skin[bi[:, k]]
                pts += bw[:, k:k + 1] * np.einsum('nij,nj->ni', m, ph)
            jts = pose[args.clip + '__joints'][f]
        rows.append([render(pts, colours, jts, parents, VIEWS[v], water=args.water) for v in ('top', 'front', 'side')])
    w = 700
    sheet = Image.new('RGB', (w * 3, w * len(rows)))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im, (c * w, r * w))
    sheet.save(args.output)
    print(args.output)


if __name__ == '__main__':
    main()
