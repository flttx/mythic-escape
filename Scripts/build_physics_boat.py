"""Integrate verified boat input with native Water buoyancy in a separate Pawn."""
import json
from ue_mcp import ROOT, UnrealMCP
from build_kraken_boat import ensure_component, reference, set_checked_properties
from verify_boat_buoyancy import call, props, BUOYANCY_SETTINGS, B, A, AC, O, S, E

BP = '/Game/MythicEscape/Chapters/Kraken/Blueprints/BP_KrakenPhysicsBoatPawn'
BASE = '/Game/MythicEscape/Chapters/Kraken/Blueprints/BP_KrakenBoatPawn'
MAP = '/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenPlayableBoatQA'
SOURCE = '/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenOceanReview'

GRAPH = '''(event EventTick (DeltaSeconds)
  (bind moveValue (Input|EnhancedActionValues|IA_Move))
  (bind lookValue (Input|EnhancedActionValues|IA_Look))
  (bind mouseLookValue (Input|EnhancedActionValues|IA_MouseLook))
  (Variables|Default|SetSteerInput (.x moveValue))
  (Variables|Default|SetThrottleInput (.y moveValue))
  (Pawn|Input|AddControllerYawInput :Val (* (.x lookValue) (Variables|Default|GetLookRate)))
  (Pawn|Input|AddControllerPitchInput :Val (* (.y lookValue) (Variables|Default|GetLookRate)))
  (Pawn|Input|AddControllerYawInput :Val (* (.x mouseLookValue) (Variables|Default|GetLookRate)))
  (Pawn|Input|AddControllerPitchInput :Val (* (.y mouseLookValue) (Variables|Default|GetLookRate)))
  (bind body (Variables|Default|GetBoatCollision))
  (bind rawForward (Transformation|GetActorForwardVector))
  ; Horizontal thrust does not push the boat underwater when it pitches.
  (bind forward (Math|Vector|MakeVector :X (.x rawForward) :Y (.y rawForward) :Z 0.0))
  (bind velocity (Physics|GetPhysicsLinearVelocity :self body))
  (bind speed (Math|Vector|DotProduct :A velocity :B forward))
  (Variables|Default|SetCurrentSpeed speed)
  (if (Variables|Default|GetControlsEnabled)
    (if (Buoyancy|IsinWaterBody :self (Variables|Default|GetOceanBuoyancy))
      (bind targetSpeed
        (select (>= (Variables|Default|GetThrottleInput) 0.0)
          (* (Variables|Default|GetThrottleInput) (Variables|Default|GetMaxForwardSpeed))
          (* (Variables|Default|GetThrottleInput) (- (Variables|Default|GetMaxReverseSpeed)))))
      (bind acceleration (Math|Float|Clamp(Float)
        :Value (* (- targetSpeed speed) 1.5) :Min -220.0 :Max 220.0))
      ; Physics integrates force over time. Do not multiply it by DeltaSeconds.
      (Physics|AddForce :self body :Force (* forward acceleration) :bAccelChange true)
      (Physics|AddTorqueinRadians :self body
        :Torque (Math|Vector|MakeVector :X 0.0 :Y 0.0
          :Z (* (Variables|Default|GetSteerInput) 1.6))
        :bAccelChange true))))'''


def author(m):
    if call(m, E, 'IsPIERunning'):
        raise RuntimeError('Stop PIE before authoring physics boat')
    call(m, B, 'get_graph_dsl_docs')
    if not call(m, A, 'exists', path=BP):
        call(m, A, 'duplicate', path=BASE, new_path=BP)
    bp = reference(BP)
    cdo = call(m, B, 'get_default_object', blueprint=bp)
    components = call(m, AC, 'get_components', actor=cdo)
    root = next(c for c in components if ':BoatCollision_' in c['refPath'])
    hull = next(c for c in components if ':HeroBoatHull_' in c['refPath'])
    camera = next(c for c in components if ':FirstPersonCamera_' in c['refPath'])
    buoy = ensure_component(m, cdo, components, 'OceanBuoyancy', '/Script/Water.BuoyancyComponent')
    set_checked_properties(m, root, {'mobility': 'Movable',
        'boxExtent': {'x': 350, 'y': 120, 'z': 60}, 'bGenerateOverlapEvents': True,
        'bodyInstance': {'collisionProfileName': 'PhysicsActor',
            'collisionEnabled': 'QueryAndPhysics', 'bSimulatePhysics': True,
            'bOverrideMass': True, 'massInKgOverride': 500,
            'linearDamping': 0.25, 'angularDamping': 1.5}})
    set_checked_properties(m, hull, {'relativeLocation': {'x': 0, 'y': 0, 'z': -20}})
    set_checked_properties(m, camera, {'relativeLocation': {'x': -175, 'y': 0, 'z': 130},
        'fieldOfView': 80, 'postProcessBlendWeight': 1,
        'postProcessSettings': {'bOverride_AutoExposureBias': True, 'autoExposureBias': 0.1}})
    set_checked_properties(m, buoy, {'buoyancyData': BUOYANCY_SETTINGS})
    set_checked_properties(m, cdo, {'maxForwardSpeed': 900, 'maxReverseSpeed': -250,
        'autoPossessPlayer': 'Player0', 'autoPossessAI': 'Disabled',
        'bUseControllerRotationYaw': False})
    call(m, B, 'compile_blueprint', blueprint=bp)
    graph = call(m, B, 'get_graph', blueprint=bp, graph_name='EventGraph')
    before = call(m, B, 'read_graph_dsl', graph=graph)
    (ROOT/'Artifacts/QA/kraken/physics-boat-before.dsl').write_text(before, encoding='utf-8')
    call(m, B, 'write_graph_dsl', graph=graph, code=GRAPH)
    call(m, B, 'compile_blueprint', blueprint=bp, warnings_as_errors=True)
    assert call(m, A, 'save_assets', asset_paths=[BP])
    if not call(m, A, 'exists', path=MAP):
        call(m, A, 'duplicate', path=SOURCE, new_path=MAP)
        assert call(m, A, 'save_assets', asset_paths=[MAP])
    if call(m, S, 'get_current_level') != MAP:
        call(m, S, 'load_level', level_path=MAP)
    actors = call(m, S, 'find_actors', name='QA_PhysicsBoat', tag='', collision_channels=[])
    # Only refresh this generated fixture, never the original hero boat/QA maps.
    for actor in actors:
        if MAP + '.' not in actor['refPath'] or '.BP_KrakenPhysicsBoatPawn_C_' not in actor['refPath']:
            raise RuntimeError('Unrelated actor matches the physics fixture label')
        assert call(m, S, 'remove_from_scene', actor=actor)
    boat = call(m, S, 'add_to_scene_from_asset', asset_path=BP, name='QA_PhysicsBoat',
        xform={'location': {'x': -35000, 'y': 0, 'z': 100}})
    if not call(m, S, 'find_actors', name='QA_BoatInput', tag='', collision_channels=[]):
        call(m, S, 'add_to_scene_from_asset',
            asset_path='/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_BoatInput',
            name='QA_BoatInput', xform={})
    for fixed_camera in call(m, S, 'find_actors', name='QA_HeroCamera', tag='', collision_channels=[]):
        set_checked_properties(m, fixed_camera, {'autoActivateForPlayer': 'Disabled'})
    for display_boat in call(m, S, 'find_actors', name='HeroBoat_TripoReview', tag='', collision_channels=[]):
        set_checked_properties(m, display_boat, {'bHidden': True})
        # Existing StaticMeshActor body reflection writes are not reliably applied
        # to PIE collision state on this editor build. Keep the comparison prop,
        # but physically move it out of the playable fixture's ocean lane.
        assert call(m, AC, 'set_actor_transform', actor=display_boat, worldspace=True,
            xform={'location': {'x': -35000, 'y': 20000, 'z': -5000}})
        for component in call(m, AC, 'get_components', actor=display_boat):
            if component['refPath'].endswith('.StaticMeshComponent0'):
                set_checked_properties(m, component, {'bodyInstance': {
                    'collisionProfileName': 'NoCollision', 'collisionEnabled': 'NoCollision'}})
    for kraken in call(m, S, 'find_actors', name='Kraken_V5_OceanReview', tag='', collision_channels=[]):
        assert call(m, AC, 'set_actor_transform', actor=kraken, worldspace=True,
            xform={'location': {'x': 24000, 'y': 0, 'z': -28000},
                   'rotation': {'pitch': 0, 'yaw': 150, 'roll': 0}})
    assert call(m, A, 'save_assets', asset_paths=[MAP])
    receipt = {'blueprint': BP, 'map': MAP, 'boat': boat, 'compiled': True,
        'runtime_verified': False, 'root': props(m, root, ['bodyInstance']),
        'buoyancy': props(m, buoy, ['buoyancyData'])}
    (ROOT/'Artifacts/QA/kraken/physics-boat-author.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print('Physics boat compiled and saved; real input and capture QA pending')


if __name__ == '__main__':
    author(UnrealMCP())
