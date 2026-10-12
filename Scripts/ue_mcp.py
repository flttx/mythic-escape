"""Local-only, project-verified UE MCP client for reproducible build/QA scripts."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
from collections.abc import Mapping

ROOT = Path(__file__).resolve().parents[1]
FIRST_PERSON_TEMPLATE_ROOT = "/game/firstperson"
BLUEPRINT_INTROSPECTION_TOOLS = frozenset({"read_graph_dsl", "get_node_type_pins"})
spec = importlib.util.spec_from_file_location(
    "mythic_capture", ROOT / ".agents/skills/mythic-visual-qa/scripts/capture_ue.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class UnrealMCP(capture.MCP):
    def __init__(self):
        if Path.cwd().resolve() != ROOT:
            raise RuntimeError("Run from Mythic Escape project root")
        self.editor_pid = capture.verify_local_project()
        super().__init__()

    def request(self, name, arguments):
        envelope = self.post("tools/call", {"name": name, "arguments": arguments})
        if not isinstance(envelope, Mapping) or "result" not in envelope:
            raise RuntimeError("Unreal MCP tools/call response had no result")
        response = envelope["result"]
        return self._decode_tool_result(response)

    @staticmethod
    def _decode_tool_result(response):
        if not isinstance(response, Mapping):
            raise RuntimeError("Unreal MCP tool result was not an object")
        UnrealMCP._raise_for_tool_error(response)

        # UE 5.8 emits this alongside a JSON text fallback. Prefer the typed value
        # so arrays, scalars, and values with a non-JSON textual representation survive.
        if "structuredContent" in response:
            structured = response["structuredContent"]
            UnrealMCP._raise_for_tool_error(structured)
            return structured

        content = response.get("content", [])
        if not isinstance(content, list):
            raise RuntimeError("Unreal MCP tool result content was not an array")
        texts = [block["text"] for block in content
                 if isinstance(block, Mapping) and block.get("type") == "text"
                 and isinstance(block.get("text"), str)]
        if len(texts) == 1:
            try:
                parsed = json.loads(texts[0])
            except json.JSONDecodeError:
                return texts[0]
            UnrealMCP._raise_for_tool_error(parsed)
            return parsed
        return response

    @staticmethod
    def _raise_for_tool_error(value):
        if not isinstance(value, Mapping) or "isError" not in value:
            return
        is_error = value["isError"]
        if not isinstance(is_error, bool):
            raise RuntimeError("Unreal MCP tool result had a non-boolean isError")
        if is_error:
            raise RuntimeError(json.dumps(value, ensure_ascii=False))

    def describe(self, toolset):
        return self.request("describe_toolset", {"toolset_name": toolset})

    def invoke(self, toolset, name, arguments=None):
        arguments = arguments or {}
        if (toolset == "BlueprintTools" or toolset.endswith(".BlueprintTools")) and name in BLUEPRINT_INTROSPECTION_TOOLS:
            if self._contains_first_person_template_path(arguments):
                raise RuntimeError(
                    f"Refusing BlueprintTools.{name} for /Game/FirstPerson: live graph introspection can corrupt "
                    "template assets. Use find_nodes or get_node_infos instead.")
        return self.request("call_tool", {"toolset_name": toolset,
            "tool_name": name, "arguments": arguments})

    @staticmethod
    def _contains_first_person_template_path(value):
        if isinstance(value, str):
            path = value.replace("\\", "/").casefold()
            return path == FIRST_PERSON_TEMPLATE_ROOT or path.startswith(FIRST_PERSON_TEMPLATE_ROOT + "/")
        if isinstance(value, Mapping):
            return any(UnrealMCP._contains_first_person_template_path(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(UnrealMCP._contains_first_person_template_path(item) for item in value)
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("toolset")
    parser.add_argument("tool", nargs="?")
    parser.add_argument("--args", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    os.chdir(ROOT)
    client = UnrealMCP()
    result = client.invoke(args.toolset, args.tool,
        json.loads(args.args.read_text(encoding="utf-8-sig")) if args.args else {}) if args.tool else client.describe(args.toolset)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(output)


if __name__ == "__main__":
    main()
