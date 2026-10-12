"""Convert armature-space clip rotations into Blender pose-bone local quaternions/locations.

PoseBone.matrix_basis is relative to the bone's own rest matrix M = [B | h] (Bone.matrix_local).
For a rest-space rotation Q about the bone head:   basis = M^-1 [Q | h - Qh] M = [B^T Q B | 0]
and for the root with translation T:                basis = [B^T Q B | B^T T].
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kraken_mesh_io as kio  # noqa: E402

KEY_STEP = 3  # key every 3rd frame at 30 fps; Bezier keys, FBX bake resamples every frame


def mat_to_quat(m):
    """(..., 3, 3) rotation matrices -> (..., 4) quaternions (w, x, y, z)."""
    w = np.sqrt(np.maximum(0, 1 + m[..., 0, 0] + m[..., 1, 1] + m[..., 2, 2])) / 2
    x = np.sqrt(np.maximum(0, 1 + m[..., 0, 0] - m[..., 1, 1] - m[..., 2, 2])) / 2
    y = np.sqrt(np.maximum(0, 1 - m[..., 0, 0] + m[..., 1, 1] - m[..., 2, 2])) / 2
    z = np.sqrt(np.maximum(0, 1 - m[..., 0, 0] - m[..., 1, 1] + m[..., 2, 2])) / 2
    x = np.copysign(x, m[..., 2, 1] - m[..., 1, 2])
    y = np.copysign(y, m[..., 0, 2] - m[..., 2, 0])
    z = np.copysign(z, m[..., 1, 0] - m[..., 0, 1])
    q = np.stack([w, x, y, z], -1)
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def main():
    rest = json.loads((HERE / 'bone_rest.json').read_text(encoding='utf-8'))['rest']
    rig = np.load(kio.CACHE / 'rig.npz')
    names = [str(n) for n in rig['names']]
    B = np.array([np.array(rest[n])[:3, :3] for n in names])
    heads_blender = np.array([np.array(rest[n])[:3, 3] for n in names])
    joint_error = float(np.abs(heads_blender - rig['heads']).max())
    orth_error = float(np.abs(np.einsum('bji,bjk->bik', B, B) - np.eye(3)).max())
    anim = np.load(kio.CACHE / 'anim.npz')
    clips = sorted({k.split('__')[0] for k in anim.files})
    out, report = {}, {'joint_head_error_m': joint_error, 'rest_orthonormal_error': orth_error, 'clips': {}}
    for clip in clips:
        rot = anim[clip + '__rot'].astype(np.float64)
        root_rot = anim[clip + '__root_rot'].astype(np.float64)
        root_t = anim[clip + '__root_t'].astype(np.float64)
        frames = np.arange(rot.shape[0])
        keys = np.unique(np.concatenate([frames[::KEY_STEP], frames[-1:]]))
        q_arm = rot[keys].copy()
        q_arm[:, 0] = root_rot[keys]
        local = np.einsum('bji,fbjk,bkl->fbil', B, q_arm, B)
        quat = mat_to_quat(local)
        for f in range(1, len(keys)):  # keep hemisphere continuity for interpolation
            flip = np.sum(quat[f] * quat[f - 1], -1) < 0
            quat[f, flip] *= -1
        loc = np.einsum('ji,fj->fi', B[0], root_t[keys])
        out[clip + '__frames'] = (keys + 1).astype(np.int32)   # Blender frames start at 1
        out[clip + '__quat'] = quat.astype(np.float32)
        out[clip + '__root_loc'] = loc.astype(np.float32)
        report['clips'][clip] = {'frames': int(rot.shape[0]), 'keys': int(len(keys))}
    out['names'] = np.array(names)
    np.savez_compressed(kio.CACHE / 'anim_blender.npz', **out)
    (HERE / 'pose_to_blender.report.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    if joint_error > 1e-3 or orth_error > 1e-4:
        raise RuntimeError('Blender rest bones do not match the derived rig')


if __name__ == '__main__':
    main()
