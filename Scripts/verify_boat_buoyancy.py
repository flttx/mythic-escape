"""Isolated native Water buoyancy fixture; no production Pawn graph changes."""
import argparse
import datetime as dt
import json
import math
import time

from ue_mcp import ROOT, UnrealMCP
from build_kraken_boat import ensure_component, reference, set_checked_properties, MESH

B = 'editor_toolset.toolsets.blueprint.BlueprintTools'
A = 'editor_toolset.toolsets.asset.AssetTools'
AC = 'editor_toolset.toolsets.actor.ActorTools'
O = 'editor_toolset.toolsets.object.ObjectTools'
S = 'editor_toolset.toolsets.scene.SceneTools'
E = 'EditorToolset.EditorAppToolset'
BP = '/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_BuoyantBoat'
MAP = '/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenBuoyancyQA'
SOURCE_MAP = '/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenOceanReview'
BUOYANCY_SETTINGS = {
    'pontoons': [{'relativeLocation': {'x': x, 'y': y, 'z': 0},
                 'radius': 100, 'bFXEnabled': True}
                for x in (-240, 240) for y in (-85, 85)],
    'bCenterPontoonsOnCOM': False,
    'buoyancyCoefficient': 0.25, 'buoyancyDamp': 1000, 'buoyancyDamp2': 1,
    'bApplyDragForcesInWater': True, 'dragCoefficient': 2,
    'dragCoefficient2': 0.01, 'angularDragCoefficient': 1,
    'bApplyRiverForces': False}


def call(m, group, tool, **args):
    return m.invoke(group, tool, args)['returnValue']


def props(m, obj, names):
    value = call(m, O, 'get_properties', instance=obj, properties=names)
    return json.loads(value) if isinstance(value, str) else value


def author(m):
    if call(m, E, 'IsPIERunning'):
        raise RuntimeError('Stop PIE before authoring')
    if not call(m, A, 'exists', path=BP):
        call(m, B, 'create', folder_path=BP.rsplit('/', 1)[0],
             asset_name=BP.rsplit('/', 1)[1], asset_type=reference('/Script/Engine.Actor'))
    bp = reference(BP)
    call(m, B, 'compile_blueprint', blueprint=bp)
    cdo = call(m, B, 'get_default_object', blueprint=bp)
    comps = call(m, AC, 'get_components', actor=cdo)
    root = ensure_component(m, cdo, comps, 'FloatRoot', '/Script/Engine.BoxComponent')
    old_root = call(m, AC, 'get_root_component', actor=cdo)
    if old_root != root:
        assert call(m, AC, 'set_parent_component', component=old_root, parent=root)
        assert call(m, AC, 'get_root_component', actor=cdo) == root
    hull = ensure_component(m, cdo, comps, 'HeroHull', '/Script/Engine.StaticMeshComponent', root)
    buoy = ensure_component(m, cdo, comps, 'OceanBuoyancy', '/Script/Water.BuoyancyComponent')
    set_checked_properties(m, root, {
        'mobility': 'Movable', 'boxExtent': {'x': 350, 'y': 120, 'z': 60},
        'bGenerateOverlapEvents': True,
        'bodyInstance': {'collisionProfileName': 'PhysicsActor',
            'collisionEnabled': 'QueryAndPhysics', 'bSimulatePhysics': True,
            'bOverrideMass': True, 'massInKgOverride': 500,
            'linearDamping': 0.25, 'angularDamping': 1.5}})
    set_checked_properties(m, hull, {'mobility': 'Movable', 'staticMesh': reference(MESH),
        'relativeLocation': {'x': 0, 'y': 0, 'z': -20},
        'bodyInstance': {'collisionProfileName': 'NoCollision'}})
    set_checked_properties(m, buoy, {'buoyancyData': BUOYANCY_SETTINGS})
    call(m, B, 'compile_blueprint', blueprint=bp, warnings_as_errors=True)
    assert call(m, A, 'save_assets', asset_paths=[BP])
    if not call(m, A, 'exists', path=MAP):
        call(m, A, 'duplicate', path=SOURCE_MAP, new_path=MAP)
        assert call(m, A, 'save_assets', asset_paths=[MAP])
    if call(m, S, 'get_current_level') != MAP:
        call(m, S, 'load_level', level_path=MAP)
    actors = call(m, S, 'find_actors', name='QA_BuoyantBoat', tag='', collision_channels=[])
    # BuoyancyData is EditDefaultsOnly. SCS reflection edits update new instances
    # only; recreate this script-owned QA fixture after preserving its Blueprint.
    for actor in actors:
        if MAP + '.' not in actor['refPath'] or '.BP_QA_BuoyantBoat_C_' not in actor['refPath']:
            raise RuntimeError('Refusing to replace an unrelated QA actor')
        assert call(m, S, 'remove_from_scene', actor=actor)
    actors = [call(m, S, 'add_to_scene_from_asset', asset_path=BP, name='QA_BuoyantBoat',
        xform={'location': {'x': -35000, 'y': 1500, 'z': 100},
               'rotation': {'pitch': 0, 'yaw': 0, 'roll': 0}})]
    assert len(actors) == 1
    live_buoy = next(c for c in call(m, AC, 'get_components', actor=actors[0])
                    if c['refPath'].endswith('.OceanBuoyancy'))
    assert abs(props(m, live_buoy, ['buoyancyData'])['buoyancyData']['buoyancyCoefficient'] - 0.25) < 0.001
    assert call(m, A, 'save_assets', asset_paths=[MAP])
    return {'blueprint': bp, 'map': MAP, 'actor': actors[0],
            'float_root': props(m, root, ['bodyInstance', 'boxExtent']),
            'buoyancy': props(m, buoy, ['buoyancyData'])}


def run(m, seconds):
    if call(m, E, 'IsPIERunning'):
        raise RuntimeError('Existing PIE must be stopped by its owner')
    level = call(m, S, 'get_current_level')
    if MAP.rsplit('/', 1)[1] not in json.dumps(level):
        raise RuntimeError('Load the isolated buoyancy QA map first')
    folder = ROOT / 'Artifacts/QA/kraken' / ('boat-buoyancy-pie-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True, exist_ok=False)
    receipt = {'map': level, 'seconds_requested': seconds, 'samples': [], 'passed': False}
    try:
        call(m, E, 'StartPIE', options={'bSimulate': False,
            'playMode': 'PlayMode_InViewPort', 'warmupSeconds': 1.0})
        time.sleep(2)
        actors = call(m, S, 'find_actors', name='QA_BuoyantBoat', tag='', collision_channels=[])
        actors = [a for a in actors if 'UEDPIE_' in a['refPath']]
        if len(actors) != 1:
            raise RuntimeError('Expected exactly one PIE buoyant boat: ' + json.dumps(actors))
        actor = actors[0]
        components = call(m, AC, 'get_components', actor=actor)
        buoy = next(c for c in components if c['refPath'].endswith('.OceanBuoyancy'))
        receipt['actor'] = actor
        receipt['runtime_config'] = props(m, buoy, ['buoyancyData'])['buoyancyData']
        root = call(m, AC, 'get_root_component', actor=actor)
        receipt['runtime_body'] = props(m, root, ['bodyInstance'])['bodyInstance']
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            transform = call(m, AC, 'get_actor_transform', actor=actor)
            data = props(m, buoy, ['buoyancyData'])['buoyancyData']
            receipt['samples'].append({'elapsed_s': time.monotonic() - start,
                'transform': transform,
                'pontoons': [{k: p.get(k) for k in ('waterHeight', 'immersionDepth',
                    'bIsInWater', 'currentWaterBodyComponent', 'localForce')}
                    for p in data['pontoons']]})
            time.sleep(0.2)
        samples = receipt['samples']
        z = [s['transform']['location']['z'] for s in samples]
        angles = [abs(s['transform']['rotation'][axis]) for s in samples for axis in ('pitch', 'roll')]
        wet = [any(p['bIsInWater'] for p in s['pontoons']) for s in samples]
        heights = [p['waterHeight'] for s in samples for p in s['pontoons'] if p['bIsInWater']]
        settled = [s for s in samples if s['elapsed_s'] >= 5]
        relative_heights = [s['transform']['location']['z'] -
            sum(p['waterHeight'] for p in s['pontoons']) / 4 for s in settled]
        forces = [sum(p['localForce']['z'] for p in s['pontoons']) for s in settled]
        vertical_speeds = [(b['transform']['location']['z'] - a['transform']['location']['z']) /
            (b['elapsed_s'] - a['elapsed_s']) for a, b in zip(settled, settled[1:])]
        mid = len(relative_heights) // 2
        relative_drift = (sum(relative_heights[mid:]) / max(1, len(relative_heights[mid:])) -
                          sum(relative_heights[:mid]) / max(1, mid))
        config = receipt['runtime_config']
        body = receipt['runtime_body']
        force_to_weight = sum(forces) / max(1, len(forces)) / (500 * 980)
        checks = {'finite_bounded_z': all(math.isfinite(v) and -500 < v < 1000 for v in z),
            'water_contact': bool(wet) and sum(wet) / len(wet) > 0.8,
            'wave_response': max(z) - min(z) > 5,
            'no_capsize': bool(angles) and max(angles) < 45,
            'water_height_changes': bool(heights) and max(heights) - min(heights) > 5,
            'runtime_config_matches': len(config['pontoons']) == 4 and
                abs(config['buoyancyCoefficient'] - 0.25) < 0.001 and
                body['bSimulatePhysics'] and body['bOverrideMass'] and
                abs(body['massInKgOverride'] - 500) < 0.01,
            'settled_sampling_window': len(settled) >= 30 and settled[-1]['elapsed_s'] >= 15,
            'buoyancy_supports_weight': 0.75 < force_to_weight < 1.25,
            'tracks_surface_without_sinking': bool(relative_heights) and
                max(abs(v) for v in relative_heights) < 100 and abs(relative_drift) < 30,
            'bounded_vertical_speed': bool(vertical_speeds) and max(abs(v) for v in vertical_speeds) < 600}
        receipt.update(checks=checks, z_range_cm=[min(z), max(z)],
            mean_buoyancy_force_to_weight=force_to_weight,
            settled_surface_offset_cm=relative_heights,
            relative_drift_cm=relative_drift,
            max_vertical_speed_cm_s=max((abs(v) for v in vertical_speeds), default=None),
            max_pitch_roll_deg=max(angles), passed=all(checks.values()))
    except Exception as exc:
        receipt['error'] = str(exc)
        raise
    finally:
        try:
            if call(m, E, 'IsPIERunning'):
                call(m, E, 'StopPIE')
            receipt['pie_stopped'] = not call(m, E, 'IsPIERunning')
            receipt['passed'] = receipt['passed'] and receipt['pie_stopped']
        except Exception as cleanup_error:
            receipt.update(cleanup_error=str(cleanup_error), pie_stopped=False, passed=False)
        (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'evidence': str(folder / 'receipt.json'), 'passed': receipt['passed'],
                          'checks': receipt.get('checks'), 'error': receipt.get('error')}))
    return receipt['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author', action='store_true')
    parser.add_argument('--run-test', action='store_true')
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    client = UnrealMCP()
    if args.author:
        result = author(client)
        (ROOT / 'Artifacts/QA/kraken/buoyant-boat-author.json').write_text(
            json.dumps(result, indent=2), encoding='utf-8')
        print('Buoyancy fixture compiled and saved')
    if args.run_test:
        raise SystemExit(0 if run(client, args.seconds) else 1)
