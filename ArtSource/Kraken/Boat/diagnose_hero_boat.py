"""Read-only post-save geometry audit and orthographic SVG diagnostic."""
import json
import sys

import bpy


def argument(name):
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return args[args.index(name) + 1]


OUT_JSON = argument("--audit")
OUT_SVG = argument("--svg")
parts = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name.startswith("SM_HeroBoat_")]
coords = [vertex.co for obj in parts for vertex in obj.data.vertices]
if not parts or not coords:
    raise RuntimeError("hero boat mesh parts not found in loaded blend")

invalid = []
for obj in parts:
    if obj.data.validate(verbose=True):
        invalid.append(obj.name)

min_x, max_x = min(v.x for v in coords), max(v.x for v in coords)
min_y, max_y = min(v.y for v in coords), max(v.y for v in coords)
min_z, max_z = min(v.z for v in coords), max(v.z for v in coords)
vertices = sum(len(obj.data.vertices) for obj in parts)
polygons = sum(len(obj.data.polygons) for obj in parts)
missing_uv = [obj.name for obj in parts if len(obj.data.uv_layers) == 0]
audit = {
    "kind": "OFFLINE_ASSET_GEOMETRY_DIAGNOSTIC_NOT_UE_VISUAL_QA",
    "parts": len(parts), "vertices": vertices, "polygons": polygons,
    "bounds_m": {"length": max_x-min_x, "beam": max_y-min_y, "height": max_z-min_z},
    "invalid_meshes_corrected_on_reopen": invalid,
    "meshes_missing_uv": missing_uv,
}
with open(OUT_JSON, "w", encoding="utf-8") as handle:
    json.dump(audit, handle, indent=2)

# A deliberately simple top/side projection of the actual reopened vertices.
def points(project, color):
    output = []
    for obj in parts:
        for vertex in obj.data.vertices:
            a, b = project(vertex.co)
            output.append('<circle cx="%.2f" cy="%.2f" r="0.7" fill="%s"/>' % (a, b, color))
    return ''.join(output)

top = lambda v: (60 + (v.x-min_x)/(max_x-min_x)*620, 150 - (v.y-min_y)/(max_y-min_y)*90)
side = lambda v: (60 + (v.x-min_x)/(max_x-min_x)*620, 350 - (v.z-min_z)/(max_z-min_z)*160)
svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="740" height="400">'
       '<rect width="100%" height="100%" fill="#101820"/>'
       '<text x="30" y="30" fill="#ffffff" font-family="sans-serif" font-size="18">HeroBoat offline mesh diagnostic - NOT UE visual QA</text>'
       '<text x="30" y="65" fill="#9fd3ff" font-family="sans-serif" font-size="14">TOP projection: curved hull / separate strakes</text>'
       '<text x="30" y="250" fill="#9fd3ff" font-family="sans-serif" font-size="14">SIDE projection: stem/stern sheer</text>'
       + points(top, '#e0a85c') + points(side, '#71c7ec') + '</svg>')
with open(OUT_SVG, "w", encoding="utf-8") as handle:
    handle.write(svg)
print("HERO_BOAT_REOPEN_AUDIT=" + json.dumps(audit))
