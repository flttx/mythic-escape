"""Offline protocol-shape tests for Scripts/ue_mcp.py."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ue_mcp", ROOT / "Scripts" / "ue_mcp.py")
ue_mcp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ue_mcp)


class UEProtocolResultTests(unittest.TestCase):
    def test_structured_content_is_returned_without_text_round_trip(self):
        payload = {"result": {"content": [{"type": "text", "text": "not JSON"}],
                              "structuredContent": {"enabled": True, "count": 2}}}
        client = object.__new__(ue_mcp.UnrealMCP)
        client.post = lambda *_: payload

        self.assertEqual(client.request("call_tool", {}), {"enabled": True, "count": 2})

    def test_nested_text_tool_error_is_not_returned_as_success(self):
        payload = {"result": {"content": [{"type": "text", "text":
                    '{"isError": true, "content": [{"type": "text", "text": "inner failure"}]}' }]}}
        client = object.__new__(ue_mcp.UnrealMCP)
        client.post = lambda *_: payload

        with self.assertRaisesRegex(RuntimeError, "inner failure"):
            client.request("call_tool", {})

    def test_nested_structured_tool_error_is_not_returned_as_success(self):
        payload = {"result": {"content": [], "structuredContent": {
            "isError": True, "content": [{"type": "text", "text": "structured failure"}]}}}
        client = object.__new__(ue_mcp.UnrealMCP)
        client.post = lambda *_: payload

        with self.assertRaisesRegex(RuntimeError, "structured failure"):
            client.request("call_tool", {})

    def test_outer_error_and_malformed_error_flag_fail_closed(self):
        for response, expected in (
            ({"isError": True, "content": [{"type": "text", "text": "outer failure"}]}, "outer failure"),
            ({"isError": "true", "content": []}, "non-boolean"),
        ):
            with self.subTest(response=response):
                with self.assertRaisesRegex(RuntimeError, expected):
                    ue_mcp.UnrealMCP._decode_tool_result(response)

    def test_missing_result_and_non_object_result_are_rejected(self):
        client = object.__new__(ue_mcp.UnrealMCP)
        for payload, expected in (({}, "no result"), ({"result": []}, "not an object")):
            with self.subTest(payload=payload):
                client.post = lambda *_args, _payload=payload: _payload
                with self.assertRaisesRegex(RuntimeError, expected):
                    client.request("call_tool", {})

    def test_template_graph_introspection_is_blocked_before_dispatch_but_safe_calls_pass(self):
        client = object.__new__(ue_mcp.UnrealMCP)
        dispatched = []
        client.request = lambda name, arguments: dispatched.append((name, arguments)) or {"ok": True}
        blueprint_tools = "editor_toolset.toolsets.blueprint.BlueprintTools"

        with self.assertRaisesRegex(RuntimeError, "can corrupt template assets"):
            client.invoke(blueprint_tools, "read_graph_dsl", {
                "graph": {"refPath": "/Game/FirstPerson/Blueprints/BP_FirstPerson.BP_FirstPerson"}})
        with self.assertRaisesRegex(RuntimeError, "get_node_infos"):
            client.invoke(blueprint_tools, "get_node_type_pins", {
                "nested": ["/game/firstperson/Blueprints/BP_FirstPerson"]})
        self.assertEqual(dispatched, [])

        self.assertEqual(client.invoke(blueprint_tools, "read_graph_dsl", {
            "graph": {"refPath": "/Game/MythicEscape/Kraken/BP_Kraken.BP_Kraken"}}), {"ok": True})
        self.assertEqual(client.invoke(blueprint_tools, "find_nodes", {
            "graph": {"refPath": "/Game/FirstPerson/Blueprints/BP_FirstPerson.BP_FirstPerson"}}), {"ok": True})
        self.assertEqual(client.invoke(blueprint_tools, "read_graph_dsl", {
            "graph": {"refPath": "/Game/FirstPersonPrototype/BP_Safe.BP_Safe"}}), {"ok": True})
        self.assertEqual(len(dispatched), 3)


if __name__ == "__main__":
    unittest.main()
