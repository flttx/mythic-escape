"""Place the skeletal V5 Kraken (Kraken_V5_Animated) in the playable boat QA map and save.

The static Kraken_V5_OceanReview keeps its asset but is parked 5 km below the sea for
comparison (reflection collision edits are unreliable in PIE for existing actors).
"""
import json

from ue_mcp import UnrealMCP
from verify_boat_buoyancy import call, props, S, O, AC, A, E
from profile_kraken_boat import MAP

RIG = '/Game/MythicEscape/Chapters/Kraken/Art/Tripo/Kraken_V5/Rig/'
MESH = RIG + 'SK_Kraken_V5.SK_Kraken_V5'
IDLE = RIG + 'SK_Kraken_V5_Anim_KrakenV5Rig_Kraken_Idle.SK_Kraken_V5_Anim_KrakenV5Rig_Kraken_Idle'
PLACEMENT = {'location': {'x': 24000, 'y': 0, 'z': -28000}, 'rotation': {'pitch': 0, 'yaw': 150, 'roll': 0},
             'scale': {'x': 1, 'y': 1, 'z': 1}}
PARKED = dict(PLACEMENT, location={'x': 24000, 'y': 0, 'z': -500000})


def find_one(m, label):
    actors = [a for a in call(m, S, 'find_actors', name=label, tag='', collision_channels=[])
              if 'UEDPIE_' not in a['refPath']]
    return actors[0] if len(actors) == 1 else None


def main():
    m = UnrealMCP()
    if call(m, E, 'IsPIERunning') or call(m, S, 'get_current_level') != MAP:
        raise RuntimeError('Requires idle ' + MAP)
    actor = find_one(m, 'Kraken_V5_Animated')
    if actor is None:
        actor = call(m, S, 'add_to_scene_from_class', actor_type={'refPath': '/Script/Engine.SkeletalMeshActor'},
                     name='Kraken_V5_Animated', xform={})
    component = next(c for c in call(m, AC, 'get_components', actor=actor)
                     if c['refPath'].endswith('.SkeletalMeshComponent0'))
    values = {'skeletalMeshAsset': {'refPath': MESH}, 'animationMode': 'AnimationSingleNode',
              'animationData': {'animToPlay': {'refPath': IDLE}, 'bSavedLooping': True, 'bSavedPlaying': True,
                                'savedPosition': 0, 'savedPlayRate': 1},
              # Keep bones evaluated off-screen: water-contact events read them every frame.
              'visibilityBasedAnimTickOption': 'AlwaysTickPoseAndRefreshBones',
              'bEnableUpdateRateOptimizations': False,
              'bodyInstance': {'collisionProfileName': 'NoCollision', 'collisionEnabled': 'NoCollision'}}
    assert call(m, O, 'set_properties', instance=component, values=json.dumps(values))
    assert call(m, AC, 'set_actor_transform', actor=actor, worldspace=True, xform=PLACEMENT)
    static = find_one(m, 'Kraken_V5_OceanReview')
    if static is not None:
        assert call(m, AC, 'set_actor_transform', actor=static, worldspace=True, xform=PARKED)
    assert call(m, A, 'save_assets', asset_paths=[MAP])
    print(json.dumps({'actor': actor, 'component': props(m, component, ['animationMode', 'animationData']),
                      'static_parked': static is not None}, indent=1))


if __name__ == '__main__':
    main()
