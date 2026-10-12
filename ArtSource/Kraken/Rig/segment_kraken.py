"""Segment the V5 Kraken mesh into mantle + arms with surface geodesic distance from the arm hub.

Output (cache/segmentation.npz): per-vertex geodesic distance from the hub sphere, part label
(-1 hub, 0 mantle, 1..8 arms) and per-part geodesic distance measured from that part's root.
"""
import heapq
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kraken_mesh_io as kio  # noqa: E402

HUB_CENTRE = np.array([80.0, -10.0, 290.0])
HUB_RADIUS = 70.0       # seed sphere: everything inside belongs to the hub/head
PART_START = 45.0       # geodesic distance beyond the hub where parts separate
MIN_PART_VERTS = 5000


def csr_adjacency(tris, n):
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    e = np.unique(e, axis=0)
    order = np.argsort(e[:, 0], kind='stable')
    e = e[order]
    indptr = np.searchsorted(e[:, 0], np.arange(n + 1))
    return indptr, e[:, 1]


def dijkstra(p, indptr, nbr, sources):
    n = len(p)
    dist = np.full(n, np.inf)
    dist[sources] = 0.0
    heap = [(0.0, int(s)) for s in sources]
    heapq.heapify(heap)
    lengths = np.linalg.norm(p[np.repeat(np.arange(n), np.diff(indptr))] - p[nbr], axis=1)
    dist_l = dist.tolist()
    indptr_l, nbr_l, len_l = indptr.tolist(), nbr.tolist(), lengths.tolist()
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist_l[u]:
            continue
        for k in range(indptr_l[u], indptr_l[u + 1]):
            v = nbr_l[k]
            nd = d + len_l[k]
            if nd < dist_l[v]:
                dist_l[v] = nd
                heapq.heappush(heap, (nd, v))
    return np.array(dist_l)


def components(mask, indptr, nbr):
    label = np.full(len(mask), -1, dtype=np.int64)
    current = 0
    nbr_l, indptr_l = nbr.tolist(), indptr.tolist()
    for start in np.flatnonzero(mask):
        if label[start] != -1:
            continue
        stack = [int(start)]
        label[start] = current
        while stack:
            u = stack.pop()
            for k in range(indptr_l[u], indptr_l[u + 1]):
                v = nbr_l[k]
                if mask[v] and label[v] == -1:
                    label[v] = current
                    stack.append(v)
        current += 1
    return label, current


def main():
    p_all, tris_all = kio.load()
    # glTF splits vertices along UV seams; weld coincident positions for surface connectivity.
    key = np.round(p_all.astype(np.float64) / 1e-3).astype(np.int64)
    _, first, weld = np.unique(key, axis=0, return_index=True, return_inverse=True)
    weld = weld.reshape(-1)
    p = p_all[first].astype(np.float64)
    tris = weld[tris_all]
    tris = tris[(tris[:, 0] != tris[:, 1]) & (tris[:, 1] != tris[:, 2]) & (tris[:, 2] != tris[:, 0])]
    indptr, nbr = csr_adjacency(tris, len(p))
    hub = np.flatnonzero(np.linalg.norm(p - HUB_CENTRE, axis=1) < HUB_RADIUS)
    dist = dijkstra(p, indptr, nbr, hub)
    unreachable = int(np.isinf(dist).sum())
    far = np.isfinite(dist) & (dist > PART_START)
    comp, count = components(far, indptr, nbr)
    sizes = np.bincount(comp[comp >= 0], minlength=count)
    big = [c for c in np.argsort(-sizes) if sizes[c] >= MIN_PART_VERTS]
    parts = []
    for c in big:
        idx = np.flatnonzero(comp == c)
        tip = idx[np.argmax(dist[idx])]
        parts.append({'component': int(c), 'vertices': int(len(idx)),
                      'max_geodesic_m': float(dist[tip]), 'tip': p[tip].round(1).tolist(),
                      'centroid': p[idx].mean(0).round(1).tolist()})
    # Mantle: the part whose centroid lies furthest towards -X (the sculpted body direction).
    mantle = min(range(len(parts)), key=lambda i: parts[i]['centroid'][0])
    order = [mantle] + [i for i in range(len(parts)) if i != mantle]
    label = np.full(len(p), -1, dtype=np.int64)
    for new, i in enumerate(order):
        label[comp == parts[i]['component']] = new
    report = {'vertices': len(p_all), 'hub_seed_vertices': int(len(hub)), 'unreachable': unreachable,
              'components_total': int(count), 'small_component_vertices': int(sizes.sum() - sum(parts[i]['vertices'] for i in order)),
              'parts': [dict(parts[i], label=new) for new, i in enumerate(order)]}
    report['welded_vertices'] = int(len(p))
    np.savez(kio.CACHE / 'segmentation.npz', dist=dist[weld].astype(np.float32), label=label[weld].astype(np.int16))
    (Path(__file__).resolve().parent / 'segmentation.report.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
