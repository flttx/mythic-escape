'''Author the input-driven Kraken boat Pawn through the verified local UE MCP editor.

This script deliberately does not alter the chapter director or place/possess an
actor in a level. Run it from the project root with the intended UE 5.8 editor
open and `-culture=en`; it creates/updates only BP_KrakenBoatPawn.
'''
import datetime as dt
import json

from ue_mcp import ROOT, UnrealMCP


BP = "/Game/MythicEscape/Chapters/Kraken/Blueprints/BP_KrakenBoatPawn"
MESH = "/Game/MythicEscape/Chapters/Kraken/Art/Tripo/Boat_V1/SM_HeroBoat_Tripo_Prepared"
TEMPLATE_CONTROLLER = "/Game/FirstPerson/Blueprints/BP_FirstPersonPlayerController"
IA_MOVE = "/Game/Input/Actions/IA_Move"
IA_LOOK = "/Game/Input/Actions/IA_Look"
IA_MOUSE_LOOK = "/Game/Input/Actions/IA_MouseLook"
B = "editor_toolset.toolsets.blueprint.BlueprintTools"
A = "editor_toolset.toolsets.asset.AssetTools"
ACTOR = "editor_toolset.toolsets.actor.ActorTools"
OBJECT = "editor_toolset.toolsets.object.ObjectTools"
EDITOR = "EditorToolset.EditorAppToolset"

SCALAR_VARIABLES = {
    "ControlsEnabled": ("bool", True),
    "WaterSurfaceZ": ("float", 0.0),
    "ThrottleInput": ("float", 0.0),
    "SteerInput": ("float", 0.0),
    "CurrentSpeed": ("float", 0.0),
    "MaxForwardSpeed": ("float", 900.0),
    "MaxReverseSpeed": ("float", -250.0),
    "Acceleration": ("float", 2.5),
    "BrakingDamping": ("float", 4.5),
    "TurnRate": ("float", 55.0),
    "LookRate": ("float", 1.0),
}

# Enhanced Input action events are intentionally absent. On this UE8001 build,
# the graph DSL writer can inspect action-event schemas while materializing them;
# that inspection is unsafe on the FirstPerson template. The existing player
# controller owns mapping contexts and this isolated Pawn reads current values.
EVENT_GRAPH = '''(event EventTick (DeltaSeconds)
  ; Release of a mapped key becomes zero without Triggered/Completed branches.
  (bind moveValue (Input|EnhancedActionValues|IA_Move))
  (bind lookValue (Input|EnhancedActionValues|IA_Look))
  (bind mouseLookValue (Input|EnhancedActionValues|IA_MouseLook))
  (Variables|Default|SetSteerInput (.x moveValue))
  (Variables|Default|SetThrottleInput (.y moveValue))
  ; Controller look stays independent from hull rotation below.
  (Pawn|Input|AddControllerYawInput :Val (* (.x lookValue) (Variables|Default|GetLookRate)))
  (Pawn|Input|AddControllerPitchInput :Val (* (.y lookValue) (Variables|Default|GetLookRate)))
  (Pawn|Input|AddControllerYawInput :Val (* (.x mouseLookValue) (Variables|Default|GetLookRate)))
  (Pawn|Input|AddControllerPitchInput :Val (* (.y mouseLookValue) (Variables|Default|GetLookRate)))
  (if (Variables|Default|GetControlsEnabled)
    (bind targetSpeed
      (select (>= (Variables|Default|GetThrottleInput) 0.0)
        (* (Variables|Default|GetThrottleInput) (Variables|Default|GetMaxForwardSpeed))
        (* (Variables|Default|GetThrottleInput) (- (Variables|Default|GetMaxReverseSpeed)))))
    (bind interpRate
      (select (== (Variables|Default|GetThrottleInput) 0.0)
        (Variables|Default|GetBrakingDamping)
        (Variables|Default|GetAcceleration)))
    (bind nextSpeed (Math|Interpolation|FInterpTo
      :Current (Variables|Default|GetCurrentSpeed)
      :Target targetSpeed
      :DeltaTime DeltaSeconds
      :InterpSpeed interpRate))
    (Variables|Default|SetCurrentSpeed nextSpeed)
    ; Steering turns this Pawn actor, while camera look only turns its controller.
    (Transformation|AddActorWorldRotation
      :DeltaRotation (Math|Rotator|MakeRotator :Yaw (* (* (Variables|Default|GetSteerInput) (Variables|Default|GetTurnRate)) DeltaSeconds))
      :bSweep true
      :bTeleport false)
    (bind forward (Transformation|GetActorForwardVector))
    (Transformation|AddActorWorldOffset
      :DeltaLocation (* (* forward nextSpeed) DeltaSeconds)
      :bSweep true
      :bTeleport false)
    (bind currentLocation (Transformation|GetActorLocation))
    ; Hold the kinematic Pawn at the authored water surface.
    (Transformation|AddActorWorldOffset
      :DeltaLocation (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z (- (Variables|Default|GetWaterSurfaceZ) (.z currentLocation)))
      :bSweep true
      :bTeleport false)))'''


def reference(path):
    return {"refPath": path if "." in path else path + "." + path.rsplit("/", 1)[-1]}


def invoke(mcp, toolset, name, arguments=None):
    return mcp.invoke(toolset, name, arguments or {})["returnValue"]


def ensure_component(mcp, cdo, components, name, class_path, parent=None):
    def is_named(item):
        tail = item["refPath"].rsplit(":", 1)[-1]
        return tail == name or tail.startswith(name + "_") or tail.startswith(name + "__")

    component = next((item for item in components if is_named(item)), None)
    if component is None:
        component = invoke(mcp, ACTOR, "add_component", {
            "owner": cdo, "component_type": reference(class_path), "name": name})
        components.append(component)
    if parent is not None:
        if not invoke(mcp, ACTOR, "set_parent_component", {"component": component, "parent": parent}):
            raise RuntimeError("Failed to attach component: " + name)
    return component


def set_checked_properties(mcp, component, values):
    raw_schema = invoke(mcp, OBJECT, "list_properties", {"instance": component})
    available = json.loads(raw_schema) if isinstance(raw_schema, str) else raw_schema
    if not isinstance(available, dict):
        raise RuntimeError("Unexpected property schema for " + component["refPath"])
    missing = set(values) - set(available)
    if missing:
        raise RuntimeError("Component property schema changed for %s: %s" %
                           (component["refPath"], sorted(missing)))
    if not invoke(mcp, OBJECT, "set_properties", {"instance": component, "values": json.dumps(values)}):
        raise RuntimeError("Failed to set properties for " + component["refPath"])


def inspect_template_controller_mapping(mcp):
    '''Read controller metadata only; never deserialize or synthesize template graph nodes.'''
    for path in (IA_MOVE, IA_LOOK, IA_MOUSE_LOOK):
        if not invoke(mcp, A, "exists", {"path": path}):
            raise RuntimeError("Required input action asset unavailable: " + path)
    controller_graph = invoke(mcp, B, "get_graph", {
        "blueprint": reference(TEMPLATE_CONTROLLER), "graph_name": "EventGraph"})
    nodes = []
    for title in ("Add Mapping Context", "AddMappingContext"):
        nodes.extend(invoke(mcp, B, "find_nodes", {
            "graph": controller_graph, "title": title, "entry_points_only": False}))
    unique = {node["refPath"]: node for node in nodes}
    if not unique:
        raise RuntimeError("Template PlayerController has no discoverable AddMappingContext node")
    return invoke(mcp, B, "get_node_infos", {"nodes": list(unique.values())})


def author(mcp, path=BP):
    if invoke(mcp, EDITOR, "IsPIERunning"):
        raise RuntimeError("Stop PIE before authoring BP_KrakenBoatPawn")
    invoke(mcp, "editor_toolset.toolsets.programmatic.ProgrammaticToolset", "get_execution_environment")
    invoke(mcp, B, "get_graph_dsl_docs")
    controller_mapping_info = inspect_template_controller_mapping(mcp)
    if not invoke(mcp, A, "exists", {"path": path}):
        invoke(mcp, B, "create", {"folder_path": path.rsplit("/", 1)[0],
                                    "asset_name": path.rsplit("/", 1)[1],
                                    "asset_type": reference("/Script/Engine.Pawn")})
    blueprint = reference(path)
    known = invoke(mcp, B, "list_variables", {"blueprint": blueprint})
    for name, (type_name, _) in SCALAR_VARIABLES.items():
        if name not in known:
            invoke(mcp, B, "add_variable", {"blueprint": blueprint, "name": name, "type_name": type_name})
    for name in SCALAR_VARIABLES:
        invoke(mcp, B, "set_variable_instance_editable", {
            "blueprint": blueprint, "variable_name": name, "instance_editable": True})
    if "Director" not in known:
        invoke(mcp, B, "add_object_variable", {"blueprint": blueprint, "name": "Director",
                                                  "object_class": reference("/Script/Engine.Actor")})
    invoke(mcp, B, "compile_blueprint", {"blueprint": blueprint})
    cdo = invoke(mcp, B, "get_default_object", {"blueprint": blueprint})
    for name, (_, default) in SCALAR_VARIABLES.items():
        if not invoke(mcp, OBJECT, "set_properties", {"instance": cdo, "values": json.dumps({name: default})}):
            raise RuntimeError("Failed to set CDO default: " + name)

    components = invoke(mcp, ACTOR, "get_components", {"actor": cdo})
    collision = ensure_component(mcp, cdo, components, "BoatCollision", "/Script/Engine.BoxComponent")
    root = invoke(mcp, ACTOR, "get_root_component", {"actor": cdo})
    if root != collision:
        if not invoke(mcp, ACTOR, "set_parent_component", {"component": root, "parent": collision}):
            raise RuntimeError("Failed to promote BoatCollision as root")
        root = invoke(mcp, ACTOR, "get_root_component", {"actor": cdo})
        if root != collision:
            raise RuntimeError("BoatCollision was not promoted to root; component hierarchy left unchanged")
    hull = ensure_component(mcp, cdo, components, "HeroBoatHull", "/Script/Engine.StaticMeshComponent", collision)
    camera = ensure_component(mcp, cdo, components, "FirstPersonCamera", "/Script/Engine.CameraComponent", collision)
    set_checked_properties(mcp, collision, {"boxExtent": {"x": 350.0, "y": 120.0, "z": 80.25},
                                            "bodyInstance": {"collisionProfileName": "BlockAll"}})
    set_checked_properties(mcp, hull, {"staticMesh": reference(MESH + ".SM_HeroBoat_Tripo_Prepared"),
                                       "bodyInstance": {"collisionProfileName": "NoCollision"}})
    set_checked_properties(mcp, camera, {"bUsePawnControlRotation": True,
                                         "relativeLocation": {"x": 25.0, "y": 0.0, "z": 130.0}})

    event_graph = invoke(mcp, B, "get_graph", {"blueprint": blueprint, "graph_name": "EventGraph"})
    catalog = {
        "TemplateControllerMapping": controller_mapping_info,
        "InputMode": "tick-polled GetIA_Move/GetIA_Look/GetIA_MouseLook; no Enhanced Input event nodes",
        "InputAssets": [IA_MOVE, IA_LOOK, IA_MOUSE_LOOK],
    }
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence = ROOT / "Artifacts/QA/kraken/boat" / stamp
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / "node_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    old = invoke(mcp, B, "read_graph_dsl", {"graph": event_graph})
    (evidence / "EventGraph.before.dsl").write_text(old, encoding="utf-8")
    invoke(mcp, B, "write_graph_dsl", {"graph": event_graph, "code": EVENT_GRAPH})
    invoke(mcp, B, "compile_blueprint", {"blueprint": blueprint, "warnings_as_errors": True})
    if not invoke(mcp, A, "save_assets", {"asset_paths": [path]}):
        raise RuntimeError("Boat pawn save failed")
    (evidence / "receipt.json").write_text(json.dumps({
        "blueprint": path, "mesh": MESH,
        "controls": "Tick polls IA_Move + IA_Look + IA_MouseLook; no Enhanced Input event nodes",
        "runtime_verified": False, "director_untouched": True}, indent=2), encoding="utf-8")
    print(evidence)


if __name__ == "__main__":
    author(UnrealMCP())
