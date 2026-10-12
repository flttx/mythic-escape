"""Read the Tripo V5 Kraken GLB with numpy in the same prepared space as SM_Kraken_Colossal_V5.

Prepared space (metres, Blender Z-up): glTF (x, y, z) -> (x, -z, y), centred on the XY
bounding box, minimum Z at 0, uniformly scaled so the larger horizontal span is 1000 m.
"""
import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
GLB = ROOT / 'ArtSource/Kraken/Tripo/KrakenV5/tripo-out/m1-kraken-redesign-v5-137eba30/model.glb'
CACHE = ROOT / 'ArtSource/Kraken/Rig/cache'
SPAN_M = 1000.0
DTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}


def _accessor(doc, binary, index):
    acc = doc['accessors'][index]
    view = doc['bufferViews'][acc['bufferView']]
    dtype = np.dtype(DTYPES[acc['componentType']])
    width = WIDTH[acc['type']]
    start = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    stride = view.get('byteStride', 0) or dtype.itemsize * width
    raw = np.frombuffer(binary, dtype=np.uint8, count=stride * (acc['count'] - 1) + dtype.itemsize * width, offset=start)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(acc['count'], dtype.itemsize * width), strides=(stride, 1))
    return np.ascontiguousarray(rows).view(dtype).reshape(acc['count'], width)


def load(use_cache=True):
    cache = CACHE / 'kraken_v5_prepared.npz'
    if use_cache and cache.exists():
        data = np.load(cache)
        return data['positions'], data['triangles']
    blob = GLB.read_bytes()
    magic, _, _ = struct.unpack_from('<III', blob, 0)
    assert magic == 0x46546C67, 'not a GLB'
    json_len, _ = struct.unpack_from('<II', blob, 12)
    doc = json.loads(blob[20:20 + json_len])
    bin_len, _ = struct.unpack_from('<II', blob, 20 + json_len)
    binary = blob[28 + json_len:28 + json_len + bin_len]
    prims = [p for m in doc['meshes'] for p in m['primitives']]
    assert len(prims) == 1, 'expected one primitive'
    g = _accessor(doc, binary, prims[0]['attributes']['POSITION']).astype(np.float64)
    tris = _accessor(doc, binary, prims[0]['indices']).reshape(-1, 3).astype(np.int64)
    b = np.stack([g[:, 0], -g[:, 2], g[:, 1]], axis=1)
    lo, hi = b.min(0), b.max(0)
    scale = SPAN_M / max(hi[0] - lo[0], hi[1] - lo[1])
    centre = (lo + hi) / 2
    p = np.empty_like(b)
    p[:, 0] = (b[:, 0] - centre[0]) * scale
    p[:, 1] = (b[:, 1] - centre[1]) * scale
    p[:, 2] = (b[:, 2] - lo[2]) * scale
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(cache, positions=p.astype(np.float32), triangles=tris.astype(np.int32))
    return p.astype(np.float32), tris.astype(np.int32)
