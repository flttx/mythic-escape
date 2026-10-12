"""Derive the V5 Kraken skeleton and skin weights from surface geodesics (numpy only).

Outputs cache/rig.npz + rig.report.json consumed by the sealed Blender assembly script:
bone names/heads/tails/parents and the top-4 skin weights for every original (unwelded)
GLB vertex. Units: metres, prepared Blender space (see kraken_mesh_io).
"""
import heapq
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kraken_mesh_io as kio  # noqa: E402
import segment_kraken as seg  # noqa: E402

SEPARATION_M = 150.0
ARM_BONES = 18
MANTLE_BONES = 5
ROOT_BLEND_M = 45.0      # arm/mantle roots blend into the head over this distance
SIGMA_BONES = 0.75       # gaussian skin falloff in bone lengths (smooth bending, no candy-wrap)
MAX_INFLUENCES = 4


def restricted_dijkstra(p, indptr, nbr, members, sources):
    inside = np.zeros(len(p), bool)
    inside[members] = True
    dist = {int(s): 0.0 for s in sources}
    heap = [(0.0, int(s)) for s in sources]
    heapq.heapify(heap)
    indptr_l, nbr_l = indptr.tolist(), nbr.tolist()
    pl = p.tolist()
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, np.inf):
            continue
        pu = pl[u]
        for k in range(indptr_l[u], indptr_l[u + 1]):
            v = nbr_l[k]
            if not inside[v]:
                continue
            pv = pl[v]
            nd = d + ((pu[0] - pv[0]) ** 2 + (pu[1] - pv[1]) ** 2 + (pu[2] - pv[2]) ** 2) ** 0.5
            if nd < dist.get(v, np.inf):
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    out = np.full(len(p), np.nan)
    keys = np.fromiter(dist.keys(), dtype=np.int64)
    out[keys] = np.fromiter(dist.values(), dtype=np.float64)
    return out


def watershed(dist, seeds, indptr, nbr):
    """Grow part labels from the separated far regions back towards the hub."""
    label = seeds.copy()
    todo = np.flatnonzero(label < 0)
    todo = todo[np.argsort(-dist[todo])]
    indptr_l, nbr_l = indptr.tolist(), nbr.tolist()
    lab = label.tolist()
    for u in todo.tolist():
        votes = {}
        for k in range(indptr_l[u], indptr_l[u + 1]):
            lv = lab[nbr_l[k]]
            if lv >= 0:
                votes[lv] = votes.get(lv, 0) + 1
        if votes:
            lab[u] = max(votes, key=votes.get)
    return np.array(lab)


def centerline(points, s, length, count):
    """Ring centroids along the part parameter, lightly smoothed, sampled at count+1 joints."""
    bins = np.linspace(0, length, 4 * count + 1)
    centres, params = [], []
    for a, b in zip(bins[:-1], bins[1:]):
        m = (s >= a) & (s < b)
        if m.sum() >= 20:
            centres.append(points[m].mean(0))
            params.append((a + b) / 2)
    centres, params = np.array(centres), np.array(params)
    kernel = np.array([1, 2, 3, 2, 1], float)
    kernel /= kernel.sum()
    padded = np.concatenate([centres[:1].repeat(2, 0), centres, centres[-1:].repeat(2, 0)])
    smooth = np.stack([np.convolve(padded[:, i], kernel, mode='valid') for i in range(3)], 1)
    targets = np.linspace(params[0], params[-1], count + 1)
    return np.stack([np.interp(targets, params, smooth[:, i]) for i in range(3)], 1), targets


def main():
    p_all, tris_all = kio.load()
    weld = np.load(kio.CACHE / 'weld.npy')
    dist = np.load(kio.CACHE / 'welded_dist.npy')
    key_first = np.full(weld.max() + 1, -1)
    key_first[weld[::-1]] = np.arange(len(weld))[::-1]
    p = p_all[key_first].astype(np.float64)
    tris = weld[tris_all]
    tris = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 2] != tris[:, 0])]
    indptr, nbr = seg.csr_adjacency(tris, len(p))

    comp, count = seg.components(dist > SEPARATION_M, indptr, nbr)
    sizes = np.bincount(comp[comp >= 0], minlength=count)
    keep = [c for c in np.argsort(-sizes) if sizes[c] > 2000]
    if len(keep) != 9:
        raise RuntimeError('Expected mantle + 8 arms, found %d parts' % len(keep))
    hub = seg.HUB_CENTRE
    info = []
    for c in keep:
        idx = np.flatnonzero(comp == c)
        tip = p[idx[np.argmax(dist[idx])]]
        info.append((c, idx, tip))
    # The mantle is the part whose far region points furthest along -X from the hub.
    mantle_c = min(info, key=lambda x: x[2][0])[0]
    arms = [x for x in info if x[0] != mantle_c]
    arms.sort(key=lambda x: np.arctan2(x[2][1] - hub[1], x[2][0] - hub[0]))
    seeds = np.full(len(p), -1)
    seeds[comp == mantle_c] = 0
    for k, (c, _, _) in enumerate(arms, start=1):
        seeds[comp == c] = k
    hub_mask = np.linalg.norm(p - hub, axis=1) < seg.HUB_RADIUS
    label = watershed(dist, np.where(hub_mask, -1, seeds), indptr, nbr)
    label[hub_mask] = -1

    names, heads, tails, parents = ['root', 'head'], [], [], [-1, 0]
    head_base = hub.copy()
    heads += [hub - [0, 0, 60.0], hub.copy()]
    tails += [hub.copy(), hub + [0, 0, 60.0]]
    parts = []
    weights = np.zeros((len(p), len(names) + 8 * ARM_BONES + MANTLE_BONES), np.float32)
    weights[label == -1, 1] = 1.0
    for part in range(9):
        members = np.flatnonzero(label == part)
        local = dist[members]
        roots = members[local <= local.min() + 3.0]
        s = restricted_dijkstra(p, indptr, nbr, members, roots)[members]
        valid = np.isfinite(s)
        length = float(np.percentile(s[valid], 99.5))
        n = MANTLE_BONES if part == 0 else ARM_BONES
        joints, stations = centerline(p[members][valid], s[valid], length, n)
        prefix = 'mantle' if part == 0 else 'arm%d' % part
        first = len(names)
        for b in range(n):
            names.append('%s_%02d' % (prefix, b))
            heads.append(joints[b])
            tails.append(joints[b + 1])
            parents.append(1 if b == 0 else len(names) - 2)
        # Skin: gaussian over bone stations, root region blended into the head bone.
        sv = np.where(valid, s, length)
        u = np.clip(sv / length, 0, 1) * n - 0.5
        centres = np.arange(n)
        g = np.exp(-0.5 * ((u[:, None] - centres[None, :]) / SIGMA_BONES) ** 2)
        g /= g.sum(1, keepdims=True)
        to_head = np.clip(1 - sv / ROOT_BLEND_M, 0, 1) ** 2
        weights[members, first:first + n] = (g * (1 - to_head)[:, None]).astype(np.float32)
        weights[members, 1] = to_head.astype(np.float32)
        parts.append({'part': prefix, 'vertices': int(len(members)), 'length_m': round(length, 1),
                      'unreached': int((~valid).sum()), 'root': joints[0].round(1).tolist(),
                      'tip': joints[-1].round(1).tolist()})
    weights = weights[:, :len(names)]
    unlabeled = int((weights.sum(1) == 0).sum())
    weights[weights.sum(1) == 0, 1] = 1.0
    top = np.argsort(-weights, axis=1)[:, :MAX_INFLUENCES]
    tw = np.take_along_axis(weights, top, 1)
    tw /= tw.sum(1, keepdims=True)
    # Map welded data back to every original GLB vertex.
    np.savez(kio.CACHE / 'rig.npz', names=np.array(names), heads=np.array(heads), tails=np.array(tails),
             parents=np.array(parents), bone_index=top[weld].astype(np.int16),
             bone_weight=tw[weld].astype(np.float32), label=label[weld].astype(np.int16))
    report = {'bones': len(names), 'parts': parts, 'hub_vertices': int(hub_mask.sum()),
              'unlabeled_welded_vertices': unlabeled, 'max_influences': MAX_INFLUENCES,
              'weight_sum_range': [float(tw.sum(1).min()), float(tw.sum(1).max())]}
    (HERE / 'rig.report.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
