"""Record native PIE CSV timings without screenshots inside the timing window."""
import argparse
import csv
import datetime as dt
import json
import shutil
import statistics
import time

from ue_mcp import ROOT, UnrealMCP
from verify_boat_buoyancy import call, props, reference, B, A, AC, O, S, E

PROBE = '/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_ViewportProbe'
MAP = '/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenPlayableBoatQA'
DSL = '''(event EventTick (DeltaSeconds)
  (bind size (Viewport|GetViewportSize))
  (Variables|Default|SetViewportWidth (.x size))
  (Variables|Default|SetViewportHeight (.y size))
  (Variables|Default|SetGameTimeSeconds (Utilities|Time|GetGameTimeinSeconds))
  (Variables|Default|SetRealTimeSeconds (Utilities|Time|GetRealTimeSeconds)))'''


def author(m):
    if call(m, E, 'IsPIERunning'):
        raise RuntimeError('Stop PIE first')
    if call(m, S, 'get_current_level') != MAP:
        raise RuntimeError('Load playable boat QA map first')
    if not call(m, A, 'exists', path=PROBE):
        call(m, B, 'create', folder_path=PROBE.rsplit('/', 1)[0],
             asset_name=PROBE.rsplit('/', 1)[1], asset_type=reference('/Script/Engine.Actor'))
    bp = reference(PROBE)
    known = call(m, B, 'list_variables', blueprint=bp)
    for name in ['ViewportWidth', 'ViewportHeight', 'GameTimeSeconds', 'RealTimeSeconds']:
        if name not in known:
            call(m, B, 'add_variable', blueprint=bp, name=name, type_name='float')
        call(m, B, 'set_variable_instance_editable', blueprint=bp, variable_name=name, instance_editable=True)
    call(m, B, 'compile_blueprint', blueprint=bp)
    graph = call(m, B, 'get_graph', blueprint=bp, graph_name='EventGraph')
    call(m, B, 'write_graph_dsl', graph=graph, code=DSL)
    call(m, B, 'compile_blueprint', blueprint=bp, warnings_as_errors=True)
    if not call(m, S, 'find_actors', name='QA_ViewportProbe', tag='', collision_channels=[]):
        call(m, S, 'add_to_scene_from_asset', asset_path=PROBE, name='QA_ViewportProbe', xform={})
    assert call(m, A, 'save_assets', asset_paths=[PROBE, MAP])


def command(m, helper, text):
    assert call(m, O, 'set_properties', instance=helper,
        values=json.dumps({'CaptureCommand': text, 'CaptureRequested': True}))
    # The helper clears the flag only after dispatching on the next game tick.
    deadline = time.monotonic() + 5
    while props(m, helper, ['CaptureRequested'])['CaptureRequested']:
        if time.monotonic() > deadline:
            raise RuntimeError('Console command did not dispatch: ' + text)
        time.sleep(0.05)


def unique_pie(m, name):
    actors = call(m, S, 'find_actors', name=name, tag='', collision_channels=[])
    actors = [a for a in actors if 'UEDPIE_' in a['refPath']]
    if len(actors) != 1:
        raise RuntimeError('Expected one runtime ' + name)
    return actors[0]


def capture(m, seconds, floating):
    if call(m, E, 'IsPIERunning'):
        raise RuntimeError('Existing PIE session belongs to its current owner')
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    folder = ROOT / 'Artifacts/QA/kraken' / ('boat-performance-' + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    filename = 'MythicEscape-Boat-' + stamp + '.csv'
    receipt = {'map': call(m, S, 'get_current_level'), 'source': 'Native PIE CSVProfiler',
        'seconds_requested': seconds, 'screenshots_in_timing_window': False,
        'conditions': 'Editor PIE, stationary player-controlled buoyant boat; not packaged acceptance',
        'gpu': 'NVIDIA GeForce RTX 3050', 'driver': '32.0.16.1062',
        'performance_status': 'NOT_MEASURED'}
    helper = None
    recording = False
    play_settings = {'refPath': '/Script/UnrealEd.Default__LevelEditorPlaySettings'}
    previous_window = None
    previous_gpu_csv = 0
    try:
        receipt['cvars_before'] = {name: call(m, E, 'SearchCVars', name=name)
            for name in ['r.GPUCsvStatsEnabled', 'r.ScreenPercentage', 'sg.ViewDistanceQuality',
                'sg.ShadowQuality', 'sg.GlobalIlluminationQuality', 'sg.ReflectionQuality',
                'sg.TextureQuality', 'sg.EffectsQuality', 'sg.PostProcessQuality', 't.MaxFPS', 'r.VSync']}
        previous_gpu_csv = json.loads(receipt['cvars_before']['r.GPUCsvStatsEnabled'])['r.GPUCsvStatsEnabled']['value']
        if floating:
            previous_window = props(m, play_settings, ['NewWindowWidth', 'NewWindowHeight'])
            assert call(m, O, 'set_properties', instance=play_settings,
                values=json.dumps({'newWindowWidth': 1920, 'newWindowHeight': 1080}))
            receipt['requested_viewport'] = [1920, 1080]
        call(m, E, 'StartPIE', options={'bSimulate': False,
             'playMode': 'PlayMode_InEditorFloating' if floating else 'PlayMode_InViewPort', 'warmupSeconds': 8})
        helper = unique_pie(m, 'QA_GameCapture')
        probe = unique_pie(m, 'QA_ViewportProbe')
        receipt['viewport'] = props(m, probe, ['ViewportWidth', 'ViewportHeight'])
        command(m, helper, 'r.GPUCsvStatsEnabled 1')
        command(m, helper, 'CsvProfile STARTFILE=' + filename)
        command(m, helper, 'CsvProfile START')
        recording = True
        time.sleep(seconds)
        command(m, helper, 'CsvProfile STOP')
        recording = False
        deadline = time.monotonic() + 10
        files = []
        while not files and time.monotonic() < deadline:
            files = list((ROOT / 'Saved/Profiling').rglob(filename))
            if not files:
                time.sleep(0.25)
        if len(files) != 1:
            raise RuntimeError('Native CSV output was not found')
        # Wait for the asynchronous CSV writer to close its file.
        time.sleep(1)
        target = folder / filename
        shutil.copy2(files[0], target)
        receipt['native_csv'] = str(files[0])
        receipt['copied_csv'] = str(target)
        with target.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
        header_index = next(i for i, row in enumerate(rows) if 'FrameTime' in row)
        header = rows[header_index]
        receipt['columns'] = header
        selected = [i for i, key in enumerate(header)
                    if any(part in key.lower() for part in ['frametime', 'gamethreadtime',
                        'renderthreadtime', 'rhithreadtime', 'gputime'])]
        metrics = {}
        for index in selected:
            values = []
            for row in rows[header_index + 1:]:
                try:
                    values.append(float(row[index]))
                except (ValueError, IndexError):
                    continue
            # Exclude CSV start/stop edge frames; no HighResShot exists in this run.
            values = values[5:-5]
            if values:
                ordered = sorted(values)
                metrics[header[index]] = {'count': len(values), 'mean_ms': statistics.mean(values),
                    'p50_ms': statistics.median(values),
                    'p95_ms': ordered[int((len(ordered) - 1) * 0.95)], 'max_ms': max(values)}
        if not metrics.get('FrameTime'):
            raise RuntimeError('CSV had no usable FrameTime samples')
        receipt.update(metrics=metrics, performance_status='MEASURED_PIE_BASELINE')
    except Exception as exc:
        receipt['error'] = str(exc)
        raise
    finally:
        try:
            if helper and call(m, E, 'IsPIERunning'):
                if recording:
                    command(m, helper, 'CsvProfile STOP')
                command(m, helper, 'r.GPUCsvStatsEnabled ' + str(previous_gpu_csv))
            if call(m, E, 'IsPIERunning'):
                call(m, E, 'StopPIE')
            receipt['pie_stopped'] = not call(m, E, 'IsPIERunning')
        except Exception as exc:
            receipt.update(cleanup_error=str(exc), pie_stopped=False)
        try:
            if previous_window is not None:
                receipt['window_settings_restored'] = call(m, O, 'set_properties',
                    instance=play_settings, values=json.dumps(previous_window))
        except Exception as exc:
            receipt['window_restore_error'] = str(exc)
        (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps({'evidence': str(folder / 'receipt.json'),
            'status': receipt['performance_status'], 'metrics': receipt.get('metrics'),
            'error': receipt.get('error')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author', action='store_true')
    parser.add_argument('--seconds', type=float, default=20)
    parser.add_argument('--floating-1080p', action='store_true')
    args = parser.parse_args()
    client = UnrealMCP()
    if args.author:
        author(client)
    capture(client, args.seconds, args.floating_1080p)
