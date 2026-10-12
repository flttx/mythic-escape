"""Apply or revert the Kraken storm environment look on the playable boat QA map.

Only lighting, sky, fog, clouds, post-process and water shading are touched; wave
shape (and therefore buoyancy) is deliberately left alone. Every value is read back
before writing so the receipt can restore it with --revert.
"""
import argparse
import datetime as dt
import json

from ue_mcp import ROOT, UnrealMCP
from verify_boat_buoyancy import call, props, S, O, AC, A, E
from profile_kraken_boat import MAP

MI = 'editor_toolset.toolsets.material_instance.MaterialInstanceTools'
L = MAP + '.' + MAP.rsplit('/', 1)[1] + ':PersistentLevel.'
OCEAN_MI = '/Game/MythicEscape/Chapters/Kraken/Environment/MI_KrakenOcean_Storm'
CLOUD_MI = '/Game/MythicEscape/Chapters/Kraken/Environment/MI_KrakenStormClouds'
PPV_NAME = 'KrakenLook_PPV'

# Low sun ahead-left of the default boat heading (+X) so the Kraken gets rim light
# and the cloud deck glows, as in the V5 concept; the old sun sat behind the camera.
SUN_ROTATION = {'pitch': -14, 'yaw': 160, 'roll': 0}

COMPONENTS = {
    # Template textured dome hid the physical SkyAtmosphere horizon.
    'StaticMeshActor_0.StaticMeshComponent0': {'bVisible': False},
    'ExponentialHeightFog_0.HeightFogComponent0': {
        'fogDensity': 0.016, 'fogHeightFalloff': 0.35, 'startDistance': 3000,
        'fogMaxOpacity': 0.95,
        'fogInscatteringLuminance': {'r': 0.032, 'g': 0.038, 'b': 0.047, 'a': 1},
        'directionalInscatteringLuminance': {'r': 0.045, 'g': 0.04, 'b': 0.034, 'a': 1},
        'directionalInscatteringExponent': 16, 'directionalInscatteringStartDistance': 2000},
    'DirectionalLight_0.LightComponent0': {
        'temperature': 6300, 'lightSourceAngle': 2.0},
    'SkyLight_0.SkyLightComponent0': {'intensity': 1.1},
}

MI_SCALARS = {
    CLOUD_MI: {'Cloud_GlobalCoverage': -0.15, 'Cloud_GlobalDensity': 0.1, 'StormClouds': 1.0},
    OCEAN_MI: {'Default Near Normal Strength': 0.85, 'Default Distant Normal Strength': 0.55},
}
MI_VECTORS = {
    OCEAN_MI: {'Scattering': {'r': 0.03, 'g': 0.042, 'b': 0.055, 'a': 0.5}},
}

PPV_SETTINGS = {
    'bOverride_ColorSaturation': True, 'colorSaturation': {'x': 0.82, 'y': 0.84, 'z': 0.88, 'w': 1},
    'bOverride_ColorContrast': True, 'colorContrast': {'x': 1.12, 'y': 1.12, 'z': 1.12, 'w': 1},
    'bOverride_ColorGammaShadows': True, 'colorGammaShadows': {'x': 0.97, 'y': 0.99, 'z': 1.03, 'w': 1},
    'bOverride_VignetteIntensity': True, 'vignetteIntensity': 0.5,
    'bOverride_BloomIntensity': True, 'bloomIntensity': 0.6,
    'bOverride_WhiteTemp': True, 'whiteTemp': 6000,
    'bOverride_AutoExposureBias': True, 'autoExposureBias': -0.4,
}


def obj(path):
    return {'refPath': path}


def mi_ref(path):
    return obj(path + '.' + path.rsplit('/', 1)[1])


def mi_get(m, kind, mat, name):
    return m.invoke(MI, 'get_%s_parameter' % kind, {'instance': mi_ref(mat), 'name': name})['returnValue']


def mi_set(m, kind, mat, name, value):
    m.invoke(MI, 'set_%s_parameter' % kind, {'instance': mi_ref(mat), 'name': name, 'value': value})
    if mi_get(m, kind, mat, name) is None:
        raise RuntimeError('Readback failed for %s %s' % (mat, name))


def find_ppv(m):
    found = [a for a in call(m, S, 'find_actors', name=PPV_NAME, tag='', collision_channels=[])
             if 'UEDPIE_' not in a['refPath']]
    return found[0] if found else None


def apply(m):
    receipt = {'map': MAP, 'components': {}, 'mi_scalars': {}, 'mi_vectors': {}}
    sun = obj(L + 'DirectionalLight_0')
    xform = call(m, AC, 'get_actor_transform', actor=sun)
    receipt['sun_transform'] = xform
    call(m, AC, 'set_actor_transform', actor=sun, worldspace=True,
         xform=dict(xform, rotation=SUN_ROTATION))
    for path, values in COMPONENTS.items():
        receipt['components'][path] = props(m, obj(L + path), list(values))
        assert call(m, O, 'set_properties', instance=obj(L + path), values=json.dumps(values))
    for mat, values in MI_SCALARS.items():
        receipt['mi_scalars'][mat] = {n: mi_get(m, 'scalar', mat, n) for n in values}
        for n, v in values.items():
            mi_set(m, 'scalar', mat, n, v)
    for mat, values in MI_VECTORS.items():
        receipt['mi_vectors'][mat] = {n: mi_get(m, 'vector', mat, n) for n in values}
        for n, v in values.items():
            mi_set(m, 'vector', mat, n, v)
    ppv = find_ppv(m)
    receipt['ppv_created'] = ppv is None
    if ppv is None:
        ppv = call(m, S, 'add_to_scene_from_class', actor_type=obj('/Script/Engine.PostProcessVolume'),
                   name=PPV_NAME, xform={})
    receipt['ppv'] = ppv
    assert call(m, O, 'set_properties', instance=ppv,
                values=json.dumps({'bUnbound': True, 'settings': PPV_SETTINGS}))
    receipt['after'] = {
        'components': {p: props(m, obj(L + p), list(v)) for p, v in COMPONENTS.items()},
        'sun_transform': call(m, AC, 'get_actor_transform', actor=sun),
        'ppv': props(m, ppv, ['bUnbound'])}
    return receipt


def revert(m, receipt):
    call(m, AC, 'set_actor_transform', actor=obj(L + 'DirectionalLight_0'), worldspace=True,
         xform=receipt['sun_transform'])
    for path, values in receipt['components'].items():
        assert call(m, O, 'set_properties', instance=obj(L + path), values=json.dumps(values))
    for kind, key in (('scalar', 'mi_scalars'), ('vector', 'mi_vectors')):
        for mat, values in receipt[key].items():
            for n, v in values.items():
                mi_set(m, kind, mat, n, v)
    ppv = find_ppv(m)
    if receipt.get('ppv_created') and ppv:
        call(m, S, 'remove_from_scene', actor=ppv)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revert', type=str, help='receipt.json written by a previous apply')
    parser.add_argument('--save', action='store_true', help='save map and the two material instances')
    args = parser.parse_args()
    m = UnrealMCP()
    if call(m, E, 'IsPIERunning') or call(m, S, 'get_current_level') != MAP:
        raise RuntimeError('Requires idle ' + MAP)
    if args.revert:
        revert(m, json.loads(open(args.revert, encoding='utf-8').read()))
        out = {'reverted': args.revert}
    else:
        folder = ROOT / 'Artifacts/QA/kraken' / ('env-look-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
        folder.mkdir(parents=True, exist_ok=False)
        receipt = apply(m)
        (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        out = {'receipt': str(folder / 'receipt.json')}
    if args.save:
        out['saved'] = call(m, A, 'save_assets', asset_paths=[MAP, OCEAN_MI, CLOUD_MI])
    print(json.dumps(out))


if __name__ == '__main__':
    main()
