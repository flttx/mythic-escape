"""Measure whether the physics boat rides the waves: camera clearance and freeboard.

Samples the possessed QA_PhysicsBoat in PIE without screenshots. Water height at the
camera is interpolated from the aft/fore pontoon queries (same CPU wave evaluation the
buoyancy uses). An optional phase caps the frame rate to reproduce long frames.
"""
import argparse
import datetime as dt
import json
import math
import time

from ue_mcp import ROOT, UnrealMCP
from verify_boat_buoyancy import call, props, AC, O, S, E
from profile_kraken_boat import command, unique_pie, MAP

EDITOR_PERF = {'refPath': '/Script/UnrealEd.Default__EditorPerformanceSettings'}
HULL_HEIGHT_CM = 160.5  # SM_HeroBoat_Tripo_Prepared local Z bounds 0..160.5 (pivot at keel)


def rotate(rotation, v):
    """Apply an Unreal FRotator (degrees) to a local vector."""
    p, y, r = (math.radians(rotation[k]) for k in ('pitch', 'yaw', 'roll'))
    sp, cp, sy, cy, sr, cr = math.sin(p), math.cos(p), math.sin(y), math.cos(y), math.sin(r), math.cos(r)
    x_axis = (cp * cy, cp * sy, sp)
    y_axis = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    z_axis = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
    return [v[0] * x_axis[i] + v[1] * y_axis[i] + v[2] * z_axis[i] for i in range(3)]


def component(m, actor, suffix):
    return next(c for c in call(m, AC, 'get_components', actor=actor) if c['refPath'].endswith(suffix))


def sample(m, boat, buoy, camera_local, hull_z, phase, start):
    xform = call(m, AC, 'get_actor_transform', actor=boat)
    data = props(m, buoy, ['buoyancyData'])['buoyancyData']['pontoons']
    loc, rot = xform['location'], xform['rotation']
    cam = rotate(rot, camera_local)
    cam_world = [loc['x'] + cam[0], loc['y'] + cam[1], loc['z'] + cam[2]]
    # A pontoon outside any water body reports a large negative sentinel height.
    if any(abs(p['waterHeight']) > 10000 for p in data):
        return {'t': time.monotonic() - start, 'phase': phase, 'z': loc['z'], 'invalid_water_query': True}
    aft = [p['waterHeight'] for p in data if p['relativeLocation']['x'] < 0]
    fore = [p['waterHeight'] for p in data if p['relativeLocation']['x'] > 0]
    aft_x = min(p['relativeLocation']['x'] for p in data)
    fore_x = max(p['relativeLocation']['x'] for p in data)
    t = (camera_local[0] - aft_x) / (fore_x - aft_x)
    water_at_camera = sum(aft) / len(aft) + (sum(fore) / len(fore) - sum(aft) / len(aft)) * t
    freeboard = []
    for p in data:
        rel = p['relativeLocation']
        gunwale = rotate(rot, [rel['x'], rel['y'], hull_z + HULL_HEIGHT_CM])
        freeboard.append(loc['z'] + gunwale[2] - p['waterHeight'])
    return {'t': time.monotonic() - start, 'phase': phase, 'z': loc['z'],
            'pitch': rot['pitch'], 'roll': rot['roll'],
            'water_at_camera_cm': water_at_camera,
            'camera_clearance_cm': cam_world[2] - water_at_camera,
            'min_freeboard_cm': min(freeboard),
            'pontoons_in_water': sum(1 for p in data if p['bIsInWater']),
            'pontoons': [[round(p['centerLocation']['z'], 1), round(p['waterHeight'], 1),
                          round(p['immersionDepth'], 1), round(p['localForce']['z'])] for p in data]}


def summarize(samples):
    invalid = sum(1 for s in samples if s.get('invalid_water_query'))
    samples = [s for s in samples if not s.get('invalid_water_query')]
    if not samples:
        return {'invalid_water_queries': invalid}
    clear = [s['camera_clearance_cm'] for s in samples]
    free = [s['min_freeboard_cm'] for s in samples]
    return {'count': len(samples), 'invalid_water_queries': invalid, 'camera_clearance_min_cm': min(clear),
            'camera_underwater_samples': sum(1 for c in clear if c < 0),
            'freeboard_min_cm': min(free), 'swamped_samples': sum(1 for f in free if f < 0),
            'airborne_samples': sum(1 for s in samples if s['pontoons_in_water'] == 0),
            'max_abs_pitch': max(abs(s['pitch']) for s in samples),
            'max_abs_roll': max(abs(s['roll']) for s in samples)}


def main(seconds, hitch_seconds, hitch_fps, warmup, label):
    m = UnrealMCP()
    if call(m, E, 'IsPIERunning') or call(m, S, 'get_current_level') != MAP:
        raise RuntimeError('Requires idle playable boat QA map')
    folder = ROOT / 'Artifacts/QA/kraken' / (label + '-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True, exist_ok=False)
    receipt = {'map': MAP, 'screenshots': False, 'samples': [], 'passed': False}
    helper = None
    previous_fps = None
    previous_throttle = props(m, EDITOR_PERF, ['bThrottleCPUWhenNotForeground'])
    try:
        # An unfocused editor otherwise caps PIE at 3 FPS and desynchronises physics from waves.
        call(m, O, 'set_properties', instance=EDITOR_PERF,
             values=json.dumps({'bThrottleCPUWhenNotForeground': False}))
        previous_fps = json.loads(call(m, E, 'SearchCVars', name='t.MaxFPS'))['t.MaxFPS']['value']
        call(m, E, 'StartPIE', options={'bSimulate': False,
             # A minimized editor throttles in-viewport PIE to 3 FPS; a floating window does not.
             'playMode': 'PlayMode_InEditorFloating', 'warmupSeconds': warmup})
        helper = unique_pie(m, 'QA_GameCapture')
        boat = unique_pie(m, 'QA_PhysicsBoat')
        buoy = component(m, boat, '.OceanBuoyancy')
        parts = call(m, AC, 'get_components', actor=boat)
        camera = next(c for c in parts if 'FirstPersonCamera' in c['refPath'].rsplit('.', 1)[-1])
        hull = next(c for c in parts if 'HeroBoatHull' in c['refPath'].rsplit('.', 1)[-1])
        cam = props(m, camera, ['relativeLocation'])['relativeLocation']
        camera_local = [cam['x'], cam['y'], cam['z']]
        hull_z = props(m, hull, ['relativeLocation'])['relativeLocation']['z']
        world_settings = {'refPath': boat['refPath'].split(':PersistentLevel.')[0] + ':PersistentLevel.WorldSettings_1'}
        receipt['timing'] = {
            'physics': props(m, {'refPath': '/Script/Engine.Default__PhysicsSettings'},
                             ['bSubstepping', 'maxSubstepDeltaTime', 'maxSubsteps', 'maxPhysicsDeltaTime']),
            'world': props(m, world_settings, ['maxUndilatedFrameTime'])}
        receipt.update(runtime_buoyancy=props(m, buoy, ['buoyancyData'])['buoyancyData'],
                       camera_local=camera_local, hull_z=hull_z)
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            receipt['samples'].append(sample(m, boat, buoy, camera_local, hull_z, 'normal', start))
        if hitch_seconds > 0:
            command(m, helper, 't.MaxFPS %g' % hitch_fps)
            hitch_start = time.monotonic()
            while time.monotonic() - hitch_start < hitch_seconds:
                receipt['samples'].append(sample(m, boat, buoy, camera_local, hull_z, 'hitch', start))
            command(m, helper, 't.MaxFPS %g' % previous_fps)
            recover = time.monotonic()
            while time.monotonic() - recover < 5:
                receipt['samples'].append(sample(m, boat, buoy, camera_local, hull_z, 'recover', start))
        receipt['summary'] = {phase: summarize([s for s in receipt['samples'] if s['phase'] == phase])
                              for phase in ('normal', 'hitch', 'recover')}
        receipt['passed'] = all(v.get('camera_underwater_samples', 0) == 0 for v in receipt['summary'].values())
    except Exception as exc:
        receipt['error'] = str(exc)
        raise
    finally:
        try:
            if helper and previous_fps is not None and call(m, E, 'IsPIERunning'):
                command(m, helper, 't.MaxFPS %g' % previous_fps)
            if call(m, E, 'IsPIERunning'):
                call(m, E, 'StopPIE')
            receipt['pie_stopped'] = not call(m, E, 'IsPIERunning')
        except Exception as exc:
            receipt.update(cleanup_error=str(exc), pie_stopped=False)
        call(m, O, 'set_properties', instance=EDITOR_PERF, values=json.dumps(previous_throttle))
        (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'receipt': str(folder / 'receipt.json'), 'passed': receipt['passed'], 'timing': receipt.get('timing'),
                          'summary': receipt.get('summary'), 'error': receipt.get('error')}, indent=1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--hitch-seconds', type=float, default=8)
    parser.add_argument('--hitch-fps', type=float, default=3)
    parser.add_argument('--warmup', type=float, default=20)
    parser.add_argument('--label', default='boat-seakeeping')
    args = parser.parse_args()
    main(args.seconds, args.hitch_seconds, args.hitch_fps, args.warmup, args.label)
