"""Save original GameViewport samples from one continuous buoyant-boat PIE run.

This is an irregularly sampled motion sequence, not a realtime video or a timing
benchmark. Capture latency is retained in the manifest instead of inventing FPS.
"""
import hashlib
import json
import datetime as dt
import struct
import time
from PIL import Image

from ue_mcp import ROOT, UnrealMCP
from verify_boat_buoyancy import call, props, AC, O, S, E
from profile_kraken_boat import command, unique_pie, MAP


def main():
    m = UnrealMCP()
    if call(m, E, 'IsPIERunning') or call(m, S, 'get_current_level') != MAP:
        raise RuntimeError('Requires idle playable boat QA map')
    folder = ROOT/'Artifacts/QA/kraken'/('boat-motion-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True, exist_ok=False)
    receipt = {'source': 'Native PIE GameViewport Shot from possessed physics boat',
        'map': MAP, 'sequence_type': 'irregularly sampled continuous PIE frames; not realtime video',
        'performance_evidence': False, 'frames': []}
    play_settings = {'refPath': '/Script/UnrealEd.Default__LevelEditorPlaySettings'}
    previous_window = props(m, play_settings, ['NewWindowWidth', 'NewWindowHeight'])
    try:
        assert call(m, O, 'set_properties', instance=play_settings,
            values=json.dumps({'newWindowWidth': 1920, 'newWindowHeight': 1080}))
        call(m, E, 'StartPIE', options={'bSimulate': False,
             'playMode': 'PlayMode_InEditorFloating', 'warmupSeconds': 8})
        helper = unique_pie(m, 'QA_GameCapture')
        boat = unique_pie(m, 'QA_PhysicsBoat')
        input_helper = unique_pie(m, 'QA_BoatInput')
        probe = unique_pie(m, 'QA_ViewportProbe')
        receipt['viewport'] = props(m, probe, ['ViewportWidth', 'ViewportHeight'])
        expected_dimensions = [int(receipt['viewport']['ViewportWidth']), int(receipt['viewport']['ViewportHeight'])]
        receipt['possession'] = props(m, input_helper,
            ['ObservedPlayerPawn', 'ObservedBoatController', 'ObservedControlledPawn'])
        if receipt['possession']['ObservedPlayerPawn'] != boat:
            raise RuntimeError('Possession did not point to the physics boat')
        components = call(m, AC, 'get_components', actor=boat)
        buoy = next(c for c in components if c['refPath'].endswith('.OceanBuoyancy'))
        start = time.monotonic()
        for i in range(4):
            out = folder / ('frame-%02d.png' % i)
            frame = {'index': i, 'request_elapsed_s': time.monotonic() - start,
                'boat_before': call(m, AC, 'get_actor_transform', actor=boat)}
            # Shot copies the existing render target; HighResShot recreates it and
            # was observed to disturb physics during repeated synchronous captures.
            command(m, helper, 'Shot -nosuffix filename="' + out.as_posix() + '"')
            deadline = time.monotonic() + 30
            while not out.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            if not out.exists():
                raise RuntimeError('GameViewport did not produce frame ' + str(i))
            time.sleep(0.2)
            with Image.open(out) as png:
                png.verify()
            data = out.read_bytes()
            frame.update(file=str(out), dimensions=list(struct.unpack('>II', data[16:24])),
                sha256=hashlib.sha256(data).hexdigest(), completed_elapsed_s=time.monotonic()-start,
                boat_after=call(m, AC, 'get_actor_transform', actor=boat),
                buoyancy=props(m, buoy, ['buoyancyData']))
            assert frame['dimensions'] == expected_dimensions
            receipt['frames'].append(frame)
            time.sleep(1)
        receipt['capture_verified'] = True
        receipt['visual_status'] = 'REQUIRES_REVIEW'
    except Exception as exc:
        receipt['error'] = str(exc)
        raise
    finally:
        try:
            if call(m, E, 'IsPIERunning'):
                call(m, E, 'StopPIE')
            receipt['pie_stopped'] = not call(m, E, 'IsPIERunning')
        except Exception as exc:
            receipt.update(stop_error=str(exc), pie_stopped=False)
        try:
            receipt['window_settings_restored'] = call(m, O, 'set_properties',
                instance=play_settings, values=json.dumps(previous_window))
        except Exception as exc:
            receipt['window_restore_error'] = str(exc)
        (folder/'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'folder': str(folder), 'frames': len(receipt['frames']),
                          'error': receipt.get('error')}))


if __name__ == '__main__':
    main()
