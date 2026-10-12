"""Build and run bounded PIE input QA for BP_KrakenBoatPawn.

The helper injects Enhanced Input values through the local-player subsystem. It
never writes movement variables on the production Pawn, modifies no template
Blueprint, and saves only BP_QA_BoatInput when explicitly built.
"""
import argparse
import datetime as dt
import json
import math
import time

from ue_mcp import ROOT, UnrealMCP


B = "editor_toolset.toolsets.blueprint.BlueprintTools"
A = "editor_toolset.toolsets.asset.AssetTools"
S = "editor_toolset.toolsets.scene.SceneTools"
O = "editor_toolset.toolsets.object.ObjectTools"
AC = "editor_toolset.toolsets.actor.ActorTools"
E = "EditorToolset.EditorAppToolset"

QA_BP = "/Game/MythicEscape/Chapters/Kraken/QA/BP_QA_BoatInput"
BOAT_BP = "/Game/MythicEscape/Chapters/Kraken/Blueprints/BP_KrakenBoatPawn"
IA_MOVE = "/Game/Input/Actions/IA_Move"
IA_LOOK = "/Game/Input/Actions/IA_Look"
WALL_NAME = "QA_BoatCollisionWall"
BOAT_START_TRANSFORM = {
    "location": {"x": -35000.0, "y": -1500.0, "z": 500.0},
    "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
}
# The QA wall is /Engine/BasicShapes/Cube: locally verified unscaled bounds ±50 cm.
CUBE_LOCAL_HALF_EXTENT_CM = 50.0
BOAT_COLLISION_HALF_LENGTH_CM = 350.0
COLLISION_TOLERANCE_CM = 5.0

HELPER_GRAPH = '''(event EventTick (DeltaSeconds)
  ; Record possession through reflected Blueprint nodes, not native Controller fields.
  (bind pc (Game|GetPlayerController :PlayerIndex 0))
  (bind pawn (Game|GetPlayerPawn :PlayerIndex 0))
  (Variables|Default|SetObservedPlayerPawn pawn)
  (Variables|Default|SetObservedBoatController (Pawn|GetController :self pawn))
  (Variables|Default|SetObservedControlledPawn (Pawn|GetControlledPawn :self pc))
  (Variables|Default|SetObservedControlRotation (Pawn|GetControlRotation :self pc))
  (if (Variables|Default|GetInjectEnabled)
    (Input|InjectInputVectorForAction
      :self (PlayerController|LocalPlayerSubsystems|GetEnhancedInputLocalPlayerSubsystem :PlayerController pc)
      :Action (Variables|Default|GetMoveAction)
      :Value (Variables|Default|GetTestMove)))
  (if (Variables|Default|GetInjectEnabled)
    (Input|InjectInputVectorForAction
      :self (PlayerController|LocalPlayerSubsystems|GetEnhancedInputLocalPlayerSubsystem :PlayerController pc)
      :Action (Variables|Default|GetLookAction)
      :Value (Variables|Default|GetTestLook))))'''


def reference(path):
    return {"refPath": path if "." in path else path + "." + path.rsplit("/", 1)[-1]}


def invoke(mcp, toolset, name, arguments=None):
    return mcp.invoke(toolset, name, arguments or {})["returnValue"]


def decode_properties(value):
    return json.loads(value) if isinstance(value, str) else value


def get_properties(mcp, instance, names):
    return decode_properties(invoke(mcp, O, "get_properties", {
        "instance": instance, "properties": names}))


def set_properties(mcp, instance, values):
    if not invoke(mcp, O, "set_properties", {"instance": instance, "values": json.dumps(values)}):
        raise RuntimeError("Failed to set QA instance properties: " + json.dumps(values))


def as_vector(x=0.0, y=0.0, z=0.0):
    return {"x": float(x), "y": float(y), "z": float(z)}


def scalar(props, name):
    value = props.get(name)
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RuntimeError("Expected finite numeric %s, got %r" % (name, value))
    return float(value)


def ref_path(value):
    if isinstance(value, dict):
        return value.get("refPath") or value.get("objectPath") or ""
    return value if isinstance(value, str) else ""


def yaw_of(transform_or_rotation):
    """Extract a yaw value from the known UE rotator shape, or fail visibly."""
    if not isinstance(transform_or_rotation, dict):
        raise RuntimeError("Expected transform/rotator object, got %r" % (transform_or_rotation,))
    rotation = transform_or_rotation.get("rotation", transform_or_rotation)
    for key in ("yaw", "Yaw"):
        if key in rotation and isinstance(rotation[key], (int, float)):
            return float(rotation[key])
    raise RuntimeError("Transform did not expose rotator yaw: " + json.dumps(transform_or_rotation))


def angle_delta_deg(before, after):
    return (after - before + 180.0) % 360.0 - 180.0


def number_at(mapping, key, label):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RuntimeError("Expected finite %s.%s, got %r" % (label, key, value))
    return float(value)


def location_x(transform):
    return number_at(transform.get("location"), "x", "transform.location")


def assert_transform_close(actual, expected, label, tolerance=0.01):
    for section, keys in (("location", ("x", "y", "z")),
                          ("rotation", ("pitch", "yaw", "roll")),
                          ("scale", ("x", "y", "z"))):
        for key in keys:
            delta = abs(number_at(actual.get(section), key, label + "." + section)
                        - number_at(expected[section], key, "expected." + section))
            if delta > tolerance:
                raise RuntimeError("%s differs at %s.%s by %.3f cm/deg" % (label, section, key, delta))


def set_actor_transform(mcp, actor, transform):
    if not invoke(mcp, AC, "set_actor_transform", {"actor": actor, "xform": transform, "worldspace": True}):
        raise RuntimeError("Actor transform reset failed: " + actor["refPath"])


def runtime_boat(mcp):
    actors = invoke(mcp, S, "find_actors", {"name": "", "tag": "", "collision_channels": []})
    boats = [actor for actor in actors if "UEDPIE_" in actor.get("refPath", "")
             and "BP_KrakenBoatPawn" in actor.get("refPath", "")]
    if len(boats) != 1:
        raise RuntimeError("Expected exactly one PIE BP_KrakenBoatPawn, got " + json.dumps(boats))
    return boats[0]


def runtime_helper(mcp):
    actors = invoke(mcp, S, "find_actors", {"name": "QA_BoatInput", "tag": "", "collision_channels": []})
    helpers = [actor for actor in actors if "UEDPIE_" in actor.get("refPath", "")]
    if len(helpers) != 1:
        raise RuntimeError("Expected exactly one PIE QA_BoatInput actor, got " + json.dumps(helpers))
    return helpers[0]


def runtime_collision_wall(mcp):
    actors = invoke(mcp, S, "find_actors", {"name": WALL_NAME, "tag": "", "collision_channels": []})
    walls = [actor for actor in actors if "UEDPIE_" in actor.get("refPath", "")]
    if len(walls) != 1:
        raise RuntimeError("Expected exactly one PIE collision wall, got " + json.dumps(walls))
    wall = walls[0]
    transform = invoke(mcp, AC, "get_actor_transform", {"actor": wall})
    expected = {"location": {"x": -33500.0, "y": -1500.0, "z": 500.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
                "scale": {"x": 1.0, "y": 20.0, "z": 10.0}}
    assert_transform_close(transform, expected, "QA collision wall")
    return wall, transform


def build_helper(mcp):
    """Author and save only the existing QA injection actor."""
    if invoke(mcp, E, "IsPIERunning"):
        raise RuntimeError("Stop PIE before authoring BP_QA_BoatInput")
    if not invoke(mcp, A, "exists", {"path": QA_BP}):
        raise RuntimeError("Required QA actor is absent: " + QA_BP)
    for path in (IA_MOVE, IA_LOOK, BOAT_BP):
        if not invoke(mcp, A, "exists", {"path": path}):
            raise RuntimeError("Required QA dependency is absent: " + path)

    blueprint = reference(QA_BP)
    variables = invoke(mcp, B, "list_variables", {"blueprint": blueprint})
    for name, type_name in (
        ("InjectEnabled", "bool"), ("TestMove", "vector"), ("TestLook", "vector"),
        ("ObservedControlRotation", "rotator"),
    ):
        if name not in variables:
            invoke(mcp, B, "add_variable", {"blueprint": blueprint, "name": name, "type_name": type_name})
        invoke(mcp, B, "set_variable_instance_editable", {
            "blueprint": blueprint, "variable_name": name, "instance_editable": True})
    for name, class_path in (
        ("ObservedPlayerPawn", "/Script/Engine.Pawn"),
        ("ObservedBoatController", "/Script/Engine.Controller"),
        ("ObservedControlledPawn", "/Script/Engine.Pawn"),
    ):
        if name not in variables:
            invoke(mcp, B, "add_object_variable", {"blueprint": blueprint, "name": name,
                "object_class": reference(class_path)})
        invoke(mcp, B, "set_variable_instance_editable", {
            "blueprint": blueprint, "variable_name": name, "instance_editable": True})
    for name in ("MoveAction", "LookAction"):
        if name not in variables:
            invoke(mcp, B, "add_object_variable", {"blueprint": blueprint, "name": name,
                "object_class": reference("/Script/EnhancedInput.InputAction")})
        invoke(mcp, B, "set_variable_instance_editable", {
            "blueprint": blueprint, "variable_name": name, "instance_editable": True})

    invoke(mcp, B, "compile_blueprint", {"blueprint": blueprint, "warnings_as_errors": True})
    cdo = invoke(mcp, B, "get_default_object", {"blueprint": blueprint})
    set_properties(mcp, cdo, {
        "InjectEnabled": False,
        "MoveAction": reference(IA_MOVE),
        "LookAction": reference(IA_LOOK),
        "TestMove": as_vector(),
        "TestLook": as_vector(),
    })
    graph = invoke(mcp, B, "get_graph", {"blueprint": blueprint, "graph_name": "EventGraph"})
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    evidence = ROOT / "Artifacts/QA/kraken" / ("boat-input-helper-" + stamp)
    evidence.mkdir(parents=True, exist_ok=False)
    before = invoke(mcp, B, "read_graph_dsl", {"graph": graph})
    (evidence / "EventGraph.before.dsl").write_text(str(before), encoding="utf-8")
    for source, target in (
        ("boat-input-node-schema.json", "inject-node-schema.json"),
        ("boat-owner-node-schema.json", "owner-node-schema.json"),
    ):
        (evidence / target).write_text(
            (ROOT / "Artifacts/QA/kraken" / source).read_text(encoding="utf-8"),
            encoding="utf-8")
    invoke(mcp, B, "write_graph_dsl", {"graph": graph, "code": HELPER_GRAPH})
    invoke(mcp, B, "compile_blueprint", {"blueprint": blueprint, "warnings_as_errors": True})
    if not invoke(mcp, A, "save_assets", {"asset_paths": [QA_BP]}):
        raise RuntimeError("QA helper save failed")
    return evidence


def run_test(mcp, warmup_seconds=1.0):
    """Execute real PIE stimulus and record measured behavior; never fabricates PASS."""
    if invoke(mcp, E, "IsPIERunning"):
        raise RuntimeError("Existing PIE session; stop it deliberately before boat input QA")
    evidence = ROOT / "Artifacts/QA/kraken" / ("boat-input-pie-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    evidence.mkdir(parents=True, exist_ok=False)
    receipt = {
        "editor_pid": mcp.editor_pid,
        "map": invoke(mcp, S, "get_current_level"),
        "source": "PIE EnhancedInputSubsystem injection via BP_QA_BoatInput",
        "production_pawn_variables_directly_written": False,
        "visual_status": "NOT_VERIFIED",
        "performance_status": "NOT_MEASURED",
    }
    try:
        invoke(mcp, E, "StartPIE", {"options": {
            "bSimulate": False, "playMode": "PlayMode_InViewPort", "warmupSeconds": warmup_seconds}})
        boat = runtime_boat(mcp)
        helper = runtime_helper(mcp)
        receipt["runtime_boat"] = boat
        receipt["runtime_helper"] = helper

        initial = get_properties(mcp, boat, ["CurrentSpeed", "SteerInput", "ThrottleInput"])
        observed = get_properties(mcp, helper, [
            "ObservedPlayerPawn", "ObservedBoatController", "ObservedControlledPawn", "ObservedControlRotation"])
        player_pawn_path = ref_path(observed.get("ObservedPlayerPawn"))
        controller_path = ref_path(observed.get("ObservedBoatController"))
        controlled_pawn_path = ref_path(observed.get("ObservedControlledPawn"))
        if player_pawn_path != boat["refPath"] or controlled_pawn_path != boat["refPath"]:
            raise RuntimeError("Helper possession observation does not identify the Boat Pawn: " + json.dumps({
                "boat": boat, "observed": observed}))
        if not controller_path or "UEDPIE_" not in controller_path:
            raise RuntimeError("Helper did not observe a PIE Boat Controller: " + json.dumps(observed))
        receipt["pawn_controller_ownership"] = {
            "boat": boat["refPath"], "player_pawn": player_pawn_path,
            "controller": controller_path, "controller_pawn": controlled_pawn_path}


        set_properties(mcp, helper, {"InjectEnabled": True,
            "TestMove": as_vector(0.0, 1.0), "TestLook": as_vector()})
        speed_start = scalar(initial, "CurrentSpeed")
        location_start = invoke(mcp, AC, "get_actor_transform", {"actor": boat})
        time.sleep(0.55)
        after_accel = get_properties(mcp, boat, ["CurrentSpeed", "ThrottleInput", "SteerInput"])
        location_after_accel = invoke(mcp, AC, "get_actor_transform", {"actor": boat})
        speed_accel = scalar(after_accel, "CurrentSpeed")
        receipt["acceleration"] = {"start_speed": speed_start, "end_speed": speed_accel,
            "input": after_accel, "start_transform": location_start,
            "end_transform": location_after_accel,
            "displacement_cm": location_x(location_after_accel) - location_x(location_start),
            "passed": speed_accel > speed_start
            and location_x(location_after_accel) - location_x(location_start) > 10.0}

        set_properties(mcp, helper, {"TestMove": as_vector(), "TestLook": as_vector()})
        time.sleep(0.55)
        after_release = get_properties(mcp, boat, ["CurrentSpeed", "ThrottleInput", "SteerInput"])
        speed_release = scalar(after_release, "CurrentSpeed")
        receipt["release_deceleration"] = {"before_release_speed": speed_accel,
            "after_release_speed": speed_release, "input": after_release,
            "passed": abs(scalar(after_release, "ThrottleInput")) < 1e-4 and abs(speed_release) < abs(speed_accel)}

        yaw_before_steer = yaw_of(invoke(mcp, AC, "get_actor_transform", {"actor": boat}))
        set_properties(mcp, helper, {"TestMove": as_vector(1.0, 0.0), "TestLook": as_vector()})
        time.sleep(0.4)
        yaw_after_steer = yaw_of(invoke(mcp, AC, "get_actor_transform", {"actor": boat}))
        steer_delta = angle_delta_deg(yaw_before_steer, yaw_after_steer)
        receipt["steering"] = {"yaw_before": yaw_before_steer, "yaw_after": yaw_after_steer,
            "delta_deg": steer_delta, "passed": abs(steer_delta) > 0.1}

        set_properties(mcp, helper, {"TestMove": as_vector(), "TestLook": as_vector(1.0, 0.0)})
        yaw_before_look = yaw_of(invoke(mcp, AC, "get_actor_transform", {"actor": boat}))
        control_before = get_properties(mcp, helper, ["ObservedControlRotation"])
        time.sleep(0.4)
        yaw_after_look = yaw_of(invoke(mcp, AC, "get_actor_transform", {"actor": boat}))
        control_after = get_properties(mcp, helper, ["ObservedControlRotation"])
        boat_look_delta = angle_delta_deg(yaw_before_look, yaw_after_look)
        control_look_delta = angle_delta_deg(yaw_of(control_before.get("ObservedControlRotation")),
                                             yaw_of(control_after.get("ObservedControlRotation")))
        receipt["look_does_not_turn_boat"] = {"boat_yaw_delta_deg": boat_look_delta,
            "controller_yaw_delta_deg": control_look_delta,
            "passed": abs(boat_look_delta) < 0.1 and abs(control_look_delta) > 0.1}

        # Reset only the QA fixture transform after the four control tests; do not
        # write production movement state. Read the wall before deriving its plane.
        set_properties(mcp, helper, {"InjectEnabled": False, "TestMove": as_vector(), "TestLook": as_vector()})
        time.sleep(0.1)
        wall, wall_transform = runtime_collision_wall(mcp)
        wall_min_x = location_x(wall_transform) - CUBE_LOCAL_HALF_EXTENT_CM * abs(
            number_at(wall_transform.get("scale"), "x", "wall.scale"))
        boat_center_max_x = wall_min_x - BOAT_COLLISION_HALF_LENGTH_CM + COLLISION_TOLERANCE_CM
        set_actor_transform(mcp, boat, BOAT_START_TRANSFORM)
        reset_transform = invoke(mcp, AC, "get_actor_transform", {"actor": boat})
        assert_transform_close(reset_transform, BOAT_START_TRANSFORM, "Boat collision reset")
        set_properties(mcp, helper, {"InjectEnabled": True,
            "TestMove": as_vector(0.0, 1.0), "TestLook": as_vector()})
        collision_samples = []
        for _ in range(25):
            time.sleep(0.1)
            sample_transform = invoke(mcp, AC, "get_actor_transform", {"actor": boat})
            collision_samples.append(location_x(sample_transform))
        collision_end = invoke(mcp, AC, "get_actor_transform", {"actor": boat})
        collision_input = get_properties(mcp, boat, ["CurrentSpeed", "ThrottleInput"])
        collision_displacement = location_x(collision_end) - location_x(reset_transform)
        collision_max_x = max(collision_samples + [location_x(collision_end)])
        receipt["collision_wall"] = {
            "wall": wall, "wall_transform": wall_transform,
            "cube_local_bounds_cm": {"min_x": -CUBE_LOCAL_HALF_EXTENT_CM, "max_x": CUBE_LOCAL_HALF_EXTENT_CM},
            "wall_min_x": wall_min_x, "boat_center_max_x": boat_center_max_x,
            "reset_transform": reset_transform, "end_transform": collision_end,
            "displacement_cm": collision_displacement, "max_center_x": collision_max_x,
            "input": collision_input,
            "passed": collision_displacement > 500.0
            and collision_max_x <= boat_center_max_x
            and abs(scalar(collision_input, "ThrottleInput") - 1.0) < 1e-4
            and scalar(collision_input, "CurrentSpeed") > 0.0,
        }

        checks = (receipt["acceleration"]["passed"], receipt["release_deceleration"]["passed"],
                  receipt["steering"]["passed"], receipt["look_does_not_turn_boat"]["passed"],
                  receipt["collision_wall"]["passed"])
        receipt["passed"] = all(checks)
        if not receipt["passed"]:
            raise RuntimeError("Boat input runtime checks failed: " + json.dumps(receipt, ensure_ascii=False))
    except Exception as exc:
        receipt["error"] = str(exc)
        receipt["passed"] = False
        raise
    finally:
        try:
            if invoke(mcp, E, "IsPIERunning"):
                invoke(mcp, E, "StopPIE")
            receipt["pie_stopped"] = not invoke(mcp, E, "IsPIERunning")
        except Exception as stop_error:
            receipt["stop_error"] = str(stop_error)
            receipt["pie_stopped"] = False
        (evidence / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if not receipt.get("pie_stopped"):
        raise RuntimeError("PIE stop was not verified; inspect " + str(evidence))
    print(json.dumps({"passed": receipt["passed"], "evidence": str(evidence)}, ensure_ascii=False))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-helper", action="store_true", help="Only author and save BP_QA_BoatInput")
    parser.add_argument("--run-test", action="store_true", help="Run only the already-built PIE QA")
    args = parser.parse_args()
    mcp = UnrealMCP()
    if args.build_helper:
        print(build_helper(mcp))
    if args.run_test:
        run_test(mcp)
    if not args.build_helper and not args.run_test:
        build_helper(mcp)
        run_test(mcp)


if __name__ == "__main__":
    main()
