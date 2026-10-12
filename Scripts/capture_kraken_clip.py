"""Play one Kraken clip from PIE start and capture irregular player-view GameViewport samples.

Sets the editor-world Kraken_V5_Animated component to the clip (PIE duplicates it), reuses
capture_boat_motion for the possessed-boat captures, then restores the looping Idle.
"""
import argparse
import json

from ue_mcp import UnrealMCP
from verify_boat_buoyancy import call, props, S, O, AC
import capture_boat_motion

RIG = '/Game/MythicEscape/Chapters/Kraken/Art/Tripo/Kraken_V5/Rig/'
CLIP = RIG + 'SK_Kraken_V5_Anim_KrakenV5Rig_{0}.SK_Kraken_V5_Anim_KrakenV5Rig_{0}'


def kraken_component(m):
    actors = [a for a in call(m, S, 'find_actors', name='Kraken_V5_Animated', tag='', collision_channels=[])
              if 'UEDPIE_' not in a['refPath']]
    if len(actors) != 1:
        raise RuntimeError('Expected one editor Kraken_V5_Animated actor')
    return next(c for c in call(m, AC, 'get_components', actor=actors[0])
                if c['refPath'].endswith('.SkeletalMeshComponent0'))


def set_clip(m, component, clip, loop, position=0.0, playing=True):
    data = {'animToPlay': {'refPath': CLIP.format(clip)}, 'bSavedLooping': loop,
            'bSavedPlaying': playing, 'savedPosition': position, 'savedPlayRate': 1}
    assert call(m, O, 'set_properties', instance=component, values=json.dumps({'animationData': data}))
    return props(m, component, ['animationData'])['animationData']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--clip', required=True, help='Kraken_Emerge | Kraken_Idle | Kraken_StrikeA | Kraken_Submerge')
    ap.add_argument('--start', type=float, default=0.0, help='clip time at PIE begin (s)')
    ap.add_argument('--frames', type=int, default=12)
    ap.add_argument('--warmup', type=float, default=6.0)
    ap.add_argument('--pause', action='store_true', help='freeze the clip at --start (pose check)')
    args = ap.parse_args()
    m = UnrealMCP()
    component = kraken_component(m)
    previous = props(m, component, ['animationData'])['animationData']
    try:
        print(set_clip(m, component, args.clip, False, args.start, not args.pause))
        label = 'kraken-%s-%s' % (args.clip.split('_', 1)[1].lower(), 'pose%.0f' % args.start if args.pause else 'play')
        capture_boat_motion.main(args.frames, label, args.warmup)
    finally:
        assert call(m, O, 'set_properties', instance=component, values=json.dumps({'animationData': previous}))


if __name__ == '__main__':
    main()
