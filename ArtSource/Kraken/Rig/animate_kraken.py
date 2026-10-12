"""Procedural Kraken performance: Idle loop, Emerge, Strike (arm4 at the boat lane), Submerge.

All motion is authored as armature-space rotations about each bone head (rest-relative) plus a
root translation, then evaluated with forward kinematics. Design rules:
  * every arm has its own phases, wave numbers and periods (harmonics of the 48 s loop), so no
    two arms move in sync and the Idle loop is seamless by construction;
  * motion travels root -> tip (phase lag), amplitude grows towards the tip;
  * transient actions are offsets on top of Idle, passed through per-bone delayed damped
    springs (heavier, slower tips) for inertia, overshoot and settle;
  * every clip starts and ends on the Idle t=0 pose (except Emerge start / Submerge end).
Units: metres / seconds / radians, prepared Blender space; sea level is local Z = 280 m in the
current QA placement (actor Z = -280 m).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kraken_mesh_io as kio  # noqa: E402

FPS = 30
LOOP_S = 48.0
W0 = 2 * np.pi / LOOP_S
SEA_Z = 280.0
DEG = np.pi / 180
# Assumed boat position in Kraken local space for the QA placement (UE imports Blender Y mirrored):
# world boat (-35000, 0) cm, Kraken actor (24000, 0) cm yaw 150 -> UE local (511, 295) m.
BOAT_LOCAL = np.array([511.0, -295.0, SEA_Z])
STRIKE_ARM = 'arm4'
RNG = np.random.default_rng(20261012)


# ---------------------------------------------------------------- rotation helpers
def axis_angle(axis, angle):
    """Rotation matrices for (..., 3) unit axes and (...) angles."""
    axis = np.asarray(axis, float)
    angle = np.asarray(angle, float)
    x, y, z = axis[..., 0], axis[..., 1], axis[..., 2]
    c, s = np.cos(angle), np.sin(angle)
    C = 1 - c
    return np.stack([
        np.stack([c + x * x * C, x * y * C - z * s, x * z * C + y * s], -1),
        np.stack([y * x * C + z * s, c + y * y * C, y * z * C - x * s], -1),
        np.stack([z * x * C - y * s, z * y * C + x * s, c + z * z * C], -1)], -2)


def smoothstep(u):
    u = np.clip(u, 0, 1)
    return u * u * u * (u * (u * 6 - 15) + 10)


class Rig:
    def __init__(self):
        r = np.load(kio.CACHE / 'rig.npz')
        self.names = [str(n) for n in r['names']]
        self.heads, self.tails, self.parents = r['heads'].astype(float), r['tails'].astype(float), r['parents']
        self.index = {n: i for i, n in enumerate(self.names)}
        d = self.tails - self.heads
        self.dirs = d / np.linalg.norm(d, axis=1, keepdims=True)
        up = np.array([0, 0, 1.0])
        curl = np.cross(self.dirs, up)
        weak = np.linalg.norm(curl, axis=1) < 0.2
        curl[weak] = np.cross(self.dirs[weak], [1.0, 0, 0])
        self.curl = curl / np.linalg.norm(curl, axis=1, keepdims=True)     # + lifts the bone towards up
        sweep = np.cross(self.curl, self.dirs)
        self.sweep = sweep / np.linalg.norm(sweep, axis=1, keepdims=True)   # sideways bend
        self.chains = {}
        for i, n in enumerate(self.names):
            if '_' in n and n != 'root':
                self.chains.setdefault(n.rsplit('_', 1)[0], []).append(i)
        self.station = np.zeros(len(self.names))  # normalised position along the chain (bone centre)
        for chain in self.chains.values():
            for k, i in enumerate(chain):
                self.station[i] = (k + 0.5) / len(chain)

    def local_rotations(self, curl, sweep, twist):
        """(frames, bones) angles -> (frames, bones, 3, 3) armature-space rotations."""
        r = axis_angle(self.curl[None], curl) @ axis_angle(self.sweep[None], sweep)
        return r @ axis_angle(self.dirs[None], twist)

    def fk(self, rot, root_rot, root_t):
        """rot: (F,B,3,3) per-bone rest-space rotations; root_rot (F,3,3); root_t (F,3).
        Returns skin affine (F,B,3,4) mapping rest points to posed points."""
        F, B = rot.shape[:2]
        A = np.zeros((F, B, 3, 3))
        b = np.zeros((F, B, 3))
        for i in range(B):
            h = self.heads[i]
            q = root_rot if self.parents[i] < 0 else rot[:, i]
            if self.parents[i] < 0:
                A[:, i] = q
                b[:, i] = h - np.einsum('fij,j->fi', q, h) + root_t
            else:
                p = self.parents[i]
                A[:, i] = A[:, p] @ q
                b[:, i] = np.einsum('fij,fj->fi', A[:, p], h - np.einsum('fij,j->fi', q, h)) + b[:, p]
        return np.concatenate([A, b[..., None]], -1)

    def joints(self, skin, which='heads'):
        pts = self.heads if which == 'heads' else self.tails
        return np.einsum('fbij,bj->fbi', skin[..., :3], pts) + skin[..., 3]


# ---------------------------------------------------------------- idle (seamless 48 s loop)
def arm_params(rig):
    params = {}
    for name in rig.chains:
        if not name.startswith('arm'):
            continue
        params[name] = {'phase': RNG.uniform(0, 2 * np.pi, 8), 'kappa': RNG.uniform(2.2, 3.4),
                        'amp': 1.0, 'sweep_amp': RNG.uniform(0.45, 0.7),
                        'tip_harmonic': int(RNG.integers(3, 6))}
    # Arms draped over the mantle (high tips) move less to avoid sliding through the body.
    for name in ('arm1', 'arm8'):
        params[name]['amp'] = 0.45
        params[name]['sweep_amp'] = 0.25
    return params


def idle_angles(rig, t, params):
    F, B = len(t), len(rig.names)
    curl, sweep, twist = np.zeros((F, B)), np.zeros((F, B)), np.zeros((F, B))
    tt = t[:, None]
    for name, chain in rig.chains.items():
        s = rig.station[chain][None, :]
        if name == 'mantle':
            # Respiration pulse (12 s) travelling down the mantle plus a slow heave.
            curl[:, chain] = 0.7 * DEG * np.sin(4 * W0 * tt - 1.4 * s) + 0.35 * DEG * np.sin(W0 * tt + 0.6)
            sweep[:, chain] = 0.4 * DEG * np.sin(2 * W0 * tt - s + 2.0)
            continue
        p = params[name]
        env = (0.12 + 0.88 * s ** 1.4) * 3.6 * DEG * p['amp']
        k, ph = p['kappa'], p['phase']
        curl[:, chain] = env * (0.55 * np.sin(2 * W0 * tt - k * s + ph[0])
                                + 0.30 * np.sin(3 * W0 * tt - 1.3 * k * s + ph[1])
                                + 0.15 * np.sin(5 * W0 * tt - 1.7 * k * s + ph[2]))
        curl[:, chain[0]] += 1.2 * DEG * p['amp'] * np.sin(2 * W0 * t + ph[3])
        # Tips curl and uncurl on their own beat (the most readable sign of life at this scale).
        tip_w = np.clip((s - 0.65) / 0.35, 0, 1) ** 2
        curl[:, chain] += 6.0 * DEG * p['amp'] * tip_w * np.sin(p['tip_harmonic'] * W0 * tt - 1.5 * s + ph[7])
        sweep[:, chain] = env * p['sweep_amp'] * (0.6 * np.sin(W0 * tt - 0.6 * k * s + ph[4])
                                                  + 0.4 * np.sin(2 * W0 * tt - 0.9 * k * s + ph[5]))
        twist[:, chain] = 0.6 * DEG * s * np.sin(3 * W0 * tt + ph[6] - 2 * s)
    head = rig.index['head']
    curl[:, head] = 0.8 * DEG * np.sin(3 * W0 * t + 0.4)
    sweep[:, head] = 0.6 * DEG * np.sin(2 * W0 * t + 1.9)
    return curl, sweep, twist


def idle_root(t):
    roll = 0.7 * DEG * np.sin(W0 * t + 0.3)
    pitch = 0.5 * DEG * np.sin(2 * W0 * t + 1.7)
    yaw = 1.0 * DEG * np.sin(W0 * t + 2.2)
    rot = axis_angle(np.array([[0, 0, 1.0]]), yaw) @ axis_angle(np.array([[0, 1.0, 0]]), pitch) \
        @ axis_angle(np.array([[1.0, 0, 0]]), roll)
    tr = np.stack([1.5 * np.sin(W0 * t), 1.0 * np.sin(W0 * t + 1.3),
                   2.5 * np.sin(2 * W0 * t) + 1.0 * np.sin(3 * W0 * t + 1.1)], 1)
    return rot, tr


# ---------------------------------------------------------------- inertia
def spring_follow(target, t, station, delay_root=0.15, delay_tip=1.4, period_root=1.3, period_tip=3.2, zeta=0.55):
    """Per-bone delayed damped spring. target: (F,B) angle offsets that start and end at 0."""
    dt = 1.0 / (FPS * 4)
    fine = np.arange(t[0], t[-1] + 1e-9, dt)
    out = np.zeros((len(fine), target.shape[1]))
    for j in range(target.shape[1]):
        s = station[j]
        delayed = np.interp(fine - (delay_root + (delay_tip - delay_root) * s ** 1.2), t, target[:, j], left=target[0, j])
        w = 2 * np.pi / (period_root + (period_tip - period_root) * s ** 1.2)
        x, v = float(target[0, j]), 0.0
        for n, g in enumerate(delayed):
            a = w * w * (g - x) - 2 * zeta * w * v
            v += a * dt
            x += v * dt
            out[n, j] = x
    res = np.stack([np.interp(t, fine, out[:, j]) for j in range(target.shape[1])], 1)
    return res


def fade_tail(series, t, duration, fade=1.5):
    """Guarantee an exact return to Idle in the last `fade` seconds."""
    w = 1 - smoothstep((t - (duration - fade)) / fade)
    return series * w.reshape((-1,) + (1,) * (series.ndim - 1))


# ---------------------------------------------------------------- strike solver
def arm_profile_angles(rig, chain, lift, curl, swing):
    s = rig.station[chain]
    wr = (1 - s) ** 1.5
    wr /= wr.sum()
    wc = s ** 1.5
    wc /= wc.sum()
    ws = (1 - s) ** 0.8
    ws /= ws.sum()
    return lift * wr + curl * wc, swing * ws


def arm_tip(rig, chain, lift, curl, swing):
    B = len(rig.names)
    c, w = np.zeros((1, B)), np.zeros((1, B))
    c[0, chain], w[0, chain] = arm_profile_angles(rig, chain, lift, curl, swing)
    rot = rig.local_rotations(c, w, np.zeros((1, B)))
    skin = rig.fk(rot, np.eye(3)[None], np.zeros((1, 3)))
    return rig.joints(skin, 'tails')[0, chain[-1]], rig.joints(skin, 'heads')[0, chain]


def solve_landing(rig, chain, target):
    best = None
    for lift in np.linspace(-20, 40, 25) * DEG:
        for curl in np.linspace(-90, 60, 31) * DEG:
            for swing in np.linspace(-80, 80, 33) * DEG:
                tip, _ = arm_tip(rig, chain, lift, curl, swing)
                err = np.linalg.norm(tip - target)
                if best is None or err < best[0]:
                    best = (err, lift, curl, swing)
    err, lift, curl, swing = best
    step = np.array([4, 6, 6]) * DEG
    x = np.array([lift, curl, swing])
    for _ in range(4):
        for _ in range(30):
            improved = False
            for dim in range(3):
                for sign in (-1, 1):
                    y = x.copy()
                    y[dim] += sign * step[dim]
                    e = np.linalg.norm(arm_tip(rig, chain, *y)[0] - target)
                    if e < err:
                        err, x, improved = e, y, True
            if not improved:
                break
        step /= 3
    return err, x


# ---------------------------------------------------------------- clips
def build_clip(rig, params, name, duration, idle_offset):
    t = np.arange(0, round(duration * FPS) + 1) / FPS
    ti = t + idle_offset
    curl, sweep, twist = idle_angles(rig, ti, params)
    root_rot, root_t = idle_root(ti)
    return t, curl, sweep, twist, root_rot, root_t


def emerge(rig, params, duration=26.0):
    t, curl, sweep, twist, root_rot, root_t = build_clip(rig, params, 'Emerge', duration, -duration)
    rise = smoothstep(t / 21.0)
    settle = np.where(t > 21.0, 3.5 * np.exp(-(t - 21.0) / 1.6) * np.sin((t - 21.0) * 2.1), 0.0)
    depth = -330.0 * (1 - rise) + settle * (1 - smoothstep((t - 23.5) / 2.5))
    root_t = root_t + np.stack([np.zeros_like(t), np.zeros_like(t), depth], 1)
    # Body rises nose (mantle) first and levels out.
    tilt = 7.0 * DEG * (1 - smoothstep((t - 4) / 16))
    root_rot = root_rot @ axis_angle(np.array([[0, 1.0, 0]]), -tilt)
    # Arms trail below while rising, then unfurl outwards (tips last).
    trail = np.zeros_like(curl)
    for cname, chain in rig.chains.items():
        if cname == 'mantle':
            continue
        s = rig.station[chain][None, :]
        unfurl = smoothstep((t[:, None] - (6 + 9 * s)) / 9.0)
        trail[:, chain] = -5.5 * DEG * (0.3 + 0.7 * s) * (1 - unfurl) * params[cname]['amp']
    trail = fade_tail(spring_follow(trail, t, rig.station, delay_tip=1.0), t, duration)
    return 'Kraken_Emerge', t, curl + trail, sweep, twist, root_rot, root_t, {'surface_break_s': float(np.interp(SEA_Z, 549 + depth, t))}


def strike(rig, params, duration=32.0):
    # Underlay runs Idle 16 s -> 48 s, so the clip ends exactly on Idle frame 0.
    t, curl, sweep, twist, root_rot, root_t = build_clip(rig, params, 'Strike', duration, LOOP_S - duration)
    chain = rig.chains[STRIKE_ARM]
    hub = rig.heads[rig.index['head']]
    to_boat = BOAT_LOCAL - hub
    to_boat[2] = 0
    to_boat /= np.linalg.norm(to_boat)
    side = np.cross([0, 0, 1.0], to_boat)
    # Readable near miss: lands 45 m short of the boat and 30 m to the side, on the water.
    target = BOAT_LOCAL - 45.0 * to_boat + 30.0 * side
    target[2] = SEA_Z + 6.0
    err, (lift_hit, curl_hit, swing_hit) = solve_landing(rig, chain, target)
    # Key poses (lift, curl, swing): rear ~200 m out of the sea, hold as the telegraph, then a
    # heavy 4.5 s accelerating fall (no faster than a free fall from that height), drag, slow retract.
    keys = [(0.0, 0, 0, 0),
            (3.5, 8 * DEG, 5 * DEG, 0.2 * swing_hit),
            (9.5, 50 * DEG, -20 * DEG, 60 * DEG),              # reared: tip ~180 m up, ~75 m from the boat
            (12.5, 52 * DEG, -10 * DEG, 62 * DEG),             # hold / coil over the player (warning)
            (14.0, 56 * DEG, -5 * DEG, 60 * DEG),              # wind-up
            (20.5, lift_hit, curl_hit, swing_hit),             # slam contact (mostly vertical drop)
            (22.5, lift_hit - 2 * DEG, curl_hit + 6 * DEG, swing_hit * 1.05),  # drag on the surface
            (30.0, 0, 0, 0)]                                   # slow retract through the water
    kt = np.array([k[0] for k in keys])

    def channel(i):
        v = np.array([k[i] for k in keys])
        out = np.zeros_like(t)
        for a in range(len(keys) - 1):
            m = (t >= kt[a]) & (t <= kt[a + 1])
            u = (t[m] - kt[a]) / (kt[a + 1] - kt[a])
            # Slam segment accelerates (heavy fall); others ease in/out.
            ease = u ** 1.6 if a == 4 else smoothstep(u)
            out[m] = v[a] + (v[a + 1] - v[a]) * ease
        out[t > kt[-1]] = 0
        return out
    lift, curl_amt, swing = channel(1), channel(2), channel(3)
    B = len(rig.names)
    c_off, w_off = np.zeros((len(t), B)), np.zeros((len(t), B))
    for f in range(len(t)):
        c_off[f, chain], w_off[f, chain] = arm_profile_angles(rig, chain, lift[f], curl_amt[f], swing[f])
    # Anticipation: the whole body leans towards the boat while rearing, recoils at the slam.
    lean = (2.5 * smoothstep((t - 2) / 8) - 4.0 * smoothstep((t - 16.5) / 4.0) + 1.5 * smoothstep((t - 21) / 7)) * DEG
    head = rig.index['head']
    c_off[:, head] += lean
    # Neighbouring arms coil slightly in agitation.
    for other in ('arm3', 'arm5'):
        ch = rig.chains[other]
        c_off[:, ch] += (4.0 * DEG * rig.station[ch][None, :] * smoothstep((t[:, None] - 2) / 4)
                         * (1 - smoothstep((t[:, None] - 21) / 7)))
    # Heavier damping / shorter lag than Idle-scale motion: the slam must not whip faster than
    # a ~240 m fall would allow (~70 m/s at impact).
    follow = dict(delay_tip=0.8, period_tip=2.6, zeta=0.75)
    c_off = fade_tail(spring_follow(c_off, t, rig.station, **follow), t, duration)
    w_off = fade_tail(spring_follow(w_off, t, rig.station, **follow), t, duration)
    meta = {'strike_arm': STRIKE_ARM, 'target_local_m': target.round(1).tolist(), 'solve_error_m': round(float(err), 2),
            'slam_key_s': 20.5, 'warning_window_s': [3.5, 14.0], 'boat_local_assumed_m': BOAT_LOCAL.tolist()}
    return 'Kraken_StrikeA', t, curl + c_off, sweep + w_off, twist, root_rot, root_t, meta


def submerge(rig, params, duration=22.0):
    t, curl, sweep, twist, root_rot, root_t = build_clip(rig, params, 'Submerge', duration, 0.0)
    sink = smoothstep((t - 4.0) / 16.0)
    root_t = root_t + np.stack([np.zeros_like(t), np.zeros_like(t), -340.0 * sink ** 1.3], 1)
    lean = 6.0 * DEG * smoothstep((t - 3) / 10)
    root_rot = root_rot @ axis_angle(np.array([[0, 1.0, 0]]), lean)
    # Arms draw inward/down first (tips lead the dive), then trail upwards as the body drops.
    off = np.zeros_like(curl)
    for cname, chain in rig.chains.items():
        if cname == 'mantle':
            continue
        s = rig.station[chain][None, :]
        gather = smoothstep((t[:, None] - 1.0 - 2.0 * (1 - s)) / 5.0)
        drag = smoothstep((t[:, None] - 9.0) / 8.0)
        off[:, chain] = (-3.5 * gather + 5.0 * drag * s) * DEG * (0.3 + 0.7 * s) * params[cname]['amp']
    off = spring_follow(off, t, rig.station, delay_tip=1.0)
    return 'Kraken_Submerge', t, curl + off, sweep, twist, root_rot, root_t, {'fully_submerged_s': 20.0}


def idle_clip(rig, params):
    t, curl, sweep, twist, root_rot, root_t = build_clip(rig, params, 'Idle', LOOP_S, 0.0)
    return 'Kraken_Idle', t, curl, sweep, twist, root_rot, root_t, {'loop_s': LOOP_S}


def main():
    rig = Rig()
    params = arm_params(rig)
    clips = [emerge(rig, params), idle_clip(rig, params), strike(rig, params), submerge(rig, params)]
    out, report = {}, {'fps': FPS, 'bones': len(rig.names), 'clips': {}}
    for name, t, curl, sweep, twist, root_rot, root_t, meta in clips:
        rot = rig.local_rotations(curl, sweep, twist)
        skin = rig.fk(rot, root_rot, root_t)
        joints = rig.joints(skin)
        tips = rig.joints(skin, 'tails')
        out[name + '__rot'] = rot.astype(np.float32)
        out[name + '__root_rot'] = root_rot.astype(np.float32)
        out[name + '__root_t'] = root_t.astype(np.float32)
        out[name + '__skin'] = skin.astype(np.float32)
        out[name + '__joints'] = joints.astype(np.float32)
        per_bone = np.degrees(np.arccos(np.clip((np.trace(rot, axis1=-2, axis2=-1) - 1) / 2, -1, 1)))
        speed = np.linalg.norm(np.diff(tips, axis=0), axis=-1) * FPS
        report['clips'][name] = dict(meta, frames=len(t), seconds=float(t[-1]),
                                     max_bone_rotation_deg=round(float(per_bone.max()), 2),
                                     max_tip_speed_mps=round(float(speed.max()), 1),
                                     root_z_range_m=[round(float(root_t[:, 2].min()), 1), round(float(root_t[:, 2].max()), 1)])
    # Seam checks: idle loop closure and clip boundaries against Idle frame 0.
    idle_j = out['Kraken_Idle__joints']
    report['idle_loop_seam_m'] = round(float(np.abs(idle_j[0] - idle_j[-1]).max()), 4)
    for name in ('Kraken_Emerge', 'Kraken_StrikeA'):
        report['clips'][name]['end_vs_idle0_m'] = round(float(np.abs(out[name + '__joints'][-1] - idle_j[0]).max()), 4)
    report['clips']['Kraken_Submerge']['start_vs_idle0_m'] = round(float(np.abs(out['Kraken_Submerge__joints'][0] - idle_j[0]).max()), 4)
    mid = int(round((LOOP_S - 32.0) * FPS))
    report['clips']['Kraken_StrikeA']['start_vs_idle16_m'] = round(float(np.abs(out['Kraken_StrikeA__joints'][0] - idle_j[mid]).max()), 4)
    np.savez_compressed(kio.CACHE / 'anim.npz', **out)
    (HERE / 'anim.report.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
