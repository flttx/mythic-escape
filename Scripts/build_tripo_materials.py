"""Connect audited original Tripo PBR maps in UE (linear ORM and GL normals)."""
import argparse
import json
from ue_mcp import ROOT, UnrealMCP

SCRIPT = '''
import json

def run():
    M = "editor_toolset.toolsets.material.MaterialTools."
    A = "editor_toolset.toolsets.asset.AssetTools."
    O = "editor_toolset.toolsets.object.ObjectTools."
    def call(name, args):
        result = execute_tool(name, json.dumps(args))
        return result.get("returnValue")
    def asset_path(ref):
        ref_path = ref.get("refPath", "") if isinstance(ref, dict) else ""
        package, separator, _ = ref_path.rpartition(".")
        return package if separator else ref_path
    refs = TEXTURE_REFS
    report = {}
    save_paths = []
    settings = {
        "BaseColor": {"sRGB": True, "compressionSettings": "TC_Default"},
        "ORM": {"sRGB": False, "compressionSettings": "TC_Masks"},
        "NormalGL": {"sRGB": False, "compressionSettings": "TC_Normalmap", "bFlipGreenChannel": True}}
    samplers = {"BaseColor": "SAMPLERTYPE_Color", "ORM": "SAMPLERTYPE_Masks", "NormalGL": "SAMPLERTYPE_Normal"}
    connections = {"BaseColor": [("RGB", "MP_BaseColor")],
                   "ORM": [("R", "MP_AmbientOcclusion"), ("G", "MP_Roughness"), ("B", "MP_Metallic")],
                   "NormalGL": [("RGB", "MP_Normal")]}
    for asset, maps in refs.items():
        folder = ASSET_FOLDERS.get(asset, "/Game/MythicEscape/Chapters/Kraken/Art/Tripo/" + asset + "_V1")
        name = "M_Hero" + asset + "_Tripo_PBR"
        path = folder + "/" + name
        save_paths.append(path)
        if not call(A + "exists", {"path": path}):
            call(M + "create_material", {"folder_path": folder, "asset_name": name})
        mat = {"refPath": path + "." + name}
        existing = call(M + "get_expressions", {"material_or_function": mat})
        by_desc = {}
        blank = []
        for node in existing:
            desc = json.loads(call(O + "get_properties", {"instance": node, "properties": ["desc"]})).get("desc", "")
            if desc:
                by_desc[desc] = node
            else:
                blank.append(node)
        report[asset] = {"material": mat, "textures": {}, "expressions": {}}
        for index, (role, texture) in enumerate(maps.items()):
            if not call(O + "set_properties", {"instance": texture, "values": json.dumps(settings[role])}):
                raise RuntimeError("Texture configuration failed: " + role)
            texture_path = asset_path(texture)
            if texture_path:
                save_paths.append(texture_path)
            desc = "TripoOriginal_" + role
            node = by_desc.get(desc)
            if node is None:
                node = blank.pop(0) if blank else call(M + "add_expression", {
                    "material_or_function": mat,
                    "expression_class": {"refPath": "/Script/Engine.MaterialExpressionTextureSample"},
                    "x": -500, "y": index * 240})
            if not call(O + "set_properties", {"instance": node, "values": json.dumps({
                    "texture": texture, "samplerType": samplers[role], "desc": desc})}):
                raise RuntimeError("Sampler configuration failed: " + role)
            for output, prop in connections[role]:
                call(M + "connect_to_output", {"expression": node, "output_name": output, "material_property": prop})
            report[asset]["textures"][role] = call(O + "get_properties", {"instance": texture, "properties": list(settings[role])})
            report[asset]["expressions"][role] = node
        call(M + "recompile", {"material_or_function": mat})
    if not call(A + "save_assets", {"asset_paths": list(dict.fromkeys(save_paths))}):
        raise RuntimeError("Material save failed")
    return report
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refs", default="Artifacts/QA/kraken/tripo-texture-refs.json")
    parser.add_argument("--folders", help="Optional JSON mapping of asset names to UE content folders")
    parser.add_argument("--output", default="Artifacts/QA/kraken/tripo-pbr-materials.json")
    args = parser.parse_args()
    m = UnrealMCP()
    toolset = "editor_toolset.toolsets.programmatic.ProgrammaticToolset"
    m.invoke(toolset, "get_execution_environment")
    refs = json.loads((ROOT / args.refs).read_text())
    folders = json.loads((ROOT / args.folders).read_text()) if args.folders else {}
    script = SCRIPT.replace("TEXTURE_REFS", repr(refs)).replace("ASSET_FOLDERS", repr(folders))
    result = m.invoke(toolset, "execute_tool_script", {"script": script})
    destination = ROOT / args.output
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(destination)
