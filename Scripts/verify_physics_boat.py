"""Run bounded PIE input QA for the native-buoyancy physics boat fixture.

This script only drives the already-authored BP_QA_BoatInput helper.  It does
not write any BP_KrakenPhysicsBoatPawn production input or movement variable.
"""
import argparse
import datetime as dt
import json
import math
import time

from ue_mcp import ROOT, UnrealMCP
from verify_boat_buoyancy import A, AC, E, O, S, call, props


MAP = "/Game/MythicEscape/Chapters/Kraken/QA/L_KrakenPlayableBoatQA"
BOAT_LABEL = "QA_PhysicsBoat"
HELPER_LABEL = "QA_BoatInput"
BOAT_CLASS_TOKEN = "BP_KrakenPhysicsBoatPawn"
SAMPLE_INTERVAL_SECONDS = 0.2
SETTLE_SECONDS = 6.0
FORWARD_SECONDS = 4.0
RELEASE_SECONDS = 4.0
STEER_SECONDS = 2.0
LOOK_SECONDS = 0.5


def ref_path(value):
    if isinstance(value, dict):
        return value.get("refPath") or value.get("objectPath") or ""
    return value if isinstance(value, str) else ""


def finite(value, label):
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RuntimeError("Expected finite %s, got %r" % (label, value))
    return float(value)


def yaw(transform):
    rotation = transform.get("rotation") if isinstance(transform, dict) else None
    if not isinstance(rotation, dict):
        raise RuntimeError("Transform has no rotation: %r" % (transform,))
    return finite(rotation.get("yaw"), "transform.rotation.yaw")


def angle_delta(before, after):
    return (after - before + 180.0) % 360.0 - 180.0


def distance_cm(before, after):
    a, b = before.get("location"), after.get("location")
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise RuntimeError("Transform has no location")
    return math.sqrt(sum((finite(b.get(axis), "end.location." + axis) -
                          finite(a.get(axis), "start.location." + axis)) ** 2
                         for axis in ("x", "y")))


def set_properties(mcp, instance, values):
    if not call(mcp, O, "set_properties", instance=instance, values=json.dumps(values)):
        raise RuntimeError("Failed to configure QA helper: " + json.dumps(values))


def pie_actor(mcp, label, expected_token):
    actors = call(mcp, S, "find_actors", name=label, tag="", collision_channels=[])
    matches = [actor for actor in actors if "UEDPIE_" in actor.get("refPath", "")
               and (expected_token is None or expected_token in actor.get("refPath", ""))]
    if len(matches) != 1:
        raise RuntimeError("Expected one PIE %s, got %s" % (label, json.dumps(matches)))
    return matches[0]


def buoyancy_component(mcp, boat):
    components = call(mcp, AC, "get_components", actor=boat)
    matches = [component for component in components
               if component.get("refPath", "").endswith(".OceanBuoyancy")]
    if len(matches) != 1:
        raise RuntimeError("Expected one OceanBuoyancy component, got " + json.dumps(matches))
    return matches[0]


def snapshot(mcp, boat, buoyancy, elapsed_s):
    data = props(mcp, buoyancy, ["buoyancyData"]).get("buoyancyData")
    if not isinstance(data, dict) or not isinstance(data.get("pontoons"), list):
        raise RuntimeError("Runtime buoyancy data did not expose pontoons: " + json.dumps(data))
    boat_props = props(mcp, boat, ["CurrentSpeed", "SteerInput", "ThrottleInput"])
    return {
        "elapsed_s": elapsed_s,
        "transform": call(mcp, AC, "get_actor_transform", actor=boat),
        "current_speed": finite(boat_props.get("CurrentSpeed"), "CurrentSpeed"),
        "steer_input": finite(boat_props.get("SteerInput"), "SteerInput"),
        "throttle_input": finite(boat_props.get("ThrottleInput"), "ThrottleInput"),
        "pontoons": [{key: pontoon.get(key) for key in
                      ("waterHeight", "immersionDepth", "bIsInWater", "localForce")}
                     for pontoon in data["pontoons"]],
    }


def sample_window(mcp, boat, buoyancy, seconds):
    start = time.monotonic()
    samples = []
    while True:
        elapsed = time.monotonic() - start
        samples.append(snapshot(mcp, boat, buoyancy, elapsed))
        if elapsed >= seconds:
            return samples
        time.sleep(min(SAMPLE_INTERVAL_SECONDS, seconds - elapsed))


def possession(mcp, boat, helper):
    observed = props(mcp, helper, ["ObservedPlayerPawn", "ObservedBoatController",
                                   "ObservedControlledPawn", "ObservedControlRotation"])
    player_pawn = ref_path(observed.get("ObservedPlayerPawn"))
    controller = ref_path(observed.get("ObservedBoatController"))
    controlled_pawn = ref_path(observed.get("ObservedControlledPawn"))
    if player_pawn != boat["refPath"] or controlled_pawn != boat["refPath"]:
        raise RuntimeError("Physics boat is not the observed player Pawn: " + json.dumps(observed))
    if "UEDPIE_" not in controller:
        raise RuntimeError("Helper did not observe a PIE controller: " + json.dumps(observed))
    return {"boat": boat["refPath"], "player_pawn": player_pawn,
            "controller": controller, "controller_pawn": controlled_pawn,
            "initial_control_rotation": observed.get("ObservedControlRotation")}


def control_rotation_yaw(mcp, helper):
    return yaw({"rotation": props(mcp, helper, ["ObservedControlRotation"])["ObservedControlRotation"]})


def run(mcp):
    if call(mcp, E, "IsPIERunning"):
        raise RuntimeError("Existing PIE session must be stopped by its owner")
    level = call(mcp, S, "get_current_level")
    if MAP.rsplit("/", 1)[1] not in json.dumps(level):
        raise RuntimeError("Load the isolated physics boat QA map first: " + MAP)
    evidence = ROOT / "Artifacts/QA/kraken" / ("physics-boat-pie-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    evidence.mkdir(parents=True, exist_ok=False)
    receipt = {"map": level, "source": "PIE Enhanced Input injection via existing BP_QA_BoatInput",
               "production_pawn_variables_directly_written": False,
               "visual_status": "NOT_VERIFIED", "performance_status": "NOT_MEASURED",
               "samples": {}, "passed": False}
    try:
        call(mcp, E, "StartPIE", options={"bSimulate": False,
             "playMode": "PlayMode_InViewPort", "warmupSeconds": 1.0})
        boat = pie_actor(mcp, BOAT_LABEL, BOAT_CLASS_TOKEN)
        helper = pie_actor(mcp, HELPER_LABEL, None)
        buoyancy = buoyancy_component(mcp, boat)
        receipt.update(runtime_boat=boat, runtime_helper=helper, buoyancy_component=buoyancy,
                       possession=possession(mcp, boat, helper))

        set_properties(mcp, helper, {"InjectEnabled": False,
                       "TestMove": {"x": 0.0, "y": 0.0, "z": 0.0},
                       "TestLook": {"x": 0.0, "y": 0.0, "z": 0.0}})
        receipt["samples"]["settle_6s"] = sample_window(mcp, boat, buoyancy, SETTLE_SECONDS)

        set_properties(mcp, helper, {"InjectEnabled": True,
                       "TestMove": {"x": 0.0, "y": 1.0, "z": 0.0},
                       "TestLook": {"x": 0.0, "y": 0.0, "z": 0.0}})
        forward = sample_window(mcp, boat, buoyancy, FORWARD_SECONDS)
        receipt["samples"]["forward_4s"] = forward
        forward_distance = distance_cm(forward[0]["transform"], forward[-1]["transform"])
        receipt["forward"] = {"distance_cm": forward_distance,
            "end_speed_cm_s": forward[-1]["current_speed"],
            "passed": forward_distance > 250.0 and forward[-1]["current_speed"] > 100.0}

        set_properties(mcp, helper, {"TestMove": {"x": 0.0, "y": 0.0, "z": 0.0},
                       "TestLook": {"x": 0.0, "y": 0.0, "z": 0.0}})
        release = sample_window(mcp, boat, buoyancy, RELEASE_SECONDS)
        receipt["samples"]["release_4s"] = release
        release_start, release_end = abs(release[0]["current_speed"]), abs(release[-1]["current_speed"])
        receipt["release"] = {"abs_speed_start_cm_s": release_start,
            "abs_speed_end_cm_s": release_end,
            "speed_reduction_cm_s": release_start - release_end,
            "passed": release_end <= release_start * 0.9 and release_start - release_end >= 20.0}

        set_properties(mcp, helper, {"TestMove": {"x": 1.0, "y": 0.0, "z": 0.0},
                       "TestLook": {"x": 0.0, "y": 0.0, "z": 0.0}})
        steering = sample_window(mcp, boat, buoyancy, STEER_SECONDS)
        receipt["samples"]["steering_2s"] = steering
        steering_delta = angle_delta(yaw(steering[0]["transform"]), yaw(steering[-1]["transform"]))
        receipt["steering"] = {"yaw_delta_deg": steering_delta, "passed": abs(steering_delta) > 5.0}

        set_properties(mcp, helper, {"TestMove": {"x": 0.0, "y": 0.0, "z": 0.0},
                       "TestLook": {"x": 0.0, "y": 0.0, "z": 0.0}})
        # Let residual rudder-induced angular momentum decay before comparing
        # a camera-only injection against the no-input wave response.
        receipt["samples"]["steering_release_2s"] = sample_window(mcp, boat, buoyancy, 2.0)
        idle_look = sample_window(mcp, boat, buoyancy, LOOK_SECONDS)
        receipt["samples"]["idle_look_baseline_0_5s"] = idle_look
        idle_yaw_delta = angle_delta(yaw(idle_look[0]["transform"]), yaw(idle_look[-1]["transform"]))
        controller_before = control_rotation_yaw(mcp, helper)
        set_properties(mcp, helper, {"TestLook": {"x": 1.0, "y": 0.0, "z": 0.0}})
        look = sample_window(mcp, boat, buoyancy, LOOK_SECONDS)
        controller_after = control_rotation_yaw(mcp, helper)
        receipt["samples"]["look_0_5s"] = look
        look_yaw_delta = angle_delta(yaw(look[0]["transform"]), yaw(look[-1]["transform"]))
        controller_delta = angle_delta(controller_before, controller_after)
        relative_body_disturbance = abs(abs(look_yaw_delta) - abs(idle_yaw_delta))
        receipt["independent_look"] = {"controller_yaw_delta_deg": controller_delta,
            "boat_yaw_delta_deg": look_yaw_delta, "idle_boat_yaw_delta_deg": idle_yaw_delta,
            "relative_body_yaw_disturbance_deg": relative_body_disturbance,
            "passed": abs(controller_delta) > 0.1 and relative_body_disturbance < 8.0}

        checks = {key: receipt[key]["passed"] for key in
                  ("forward", "release", "steering", "independent_look")}
        receipt["checks"] = checks
        receipt["passed"] = all(checks.values())
        if not receipt["passed"]:
            raise RuntimeError("Physics boat checks failed: " + json.dumps(checks))
    except Exception as exc:
        receipt["error"] = str(exc)
        receipt["passed"] = False
        raise
    finally:
        try:
            if call(mcp, E, "IsPIERunning"):
                call(mcp, E, "StopPIE")
            receipt["pie_stopped"] = not call(mcp, E, "IsPIERunning")
        except Exception as stop_error:
            receipt["stop_error"] = str(stop_error)
            receipt["pie_stopped"] = False
        receipt["passed"] = receipt["passed"] and receipt["pie_stopped"]
        (evidence / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    if not receipt.get("pie_stopped"):
        raise RuntimeError("PIE stop was not verified; inspect " + str(evidence))
    print(json.dumps({"passed": receipt["passed"], "evidence": str(evidence)}, ensure_ascii=False))
    return receipt["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-test", action="store_true", help="Run the authored physics-boat PIE QA")
    args = parser.parse_args()
    if not args.run_test:
        parser.error("Use --run-test; this script never authors UE assets")
    raise SystemExit(0 if run(UnrealMCP()) else 1)
