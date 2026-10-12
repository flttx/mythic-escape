"""Extract original embedded PBR images without resizing or pixel modification."""
import argparse
import hashlib
import json

from inspect_glb_asset import buffer_view_bytes, parse_glb, project_path, image_dimensions


def extract(source, destination, prefix):
    _, doc, bins, _ = parse_glb(source)
    if len(doc.get("materials", [])) != 1:
        raise ValueError("This scoped importer requires one material; inspect multi-material assets separately")
    mat = doc["materials"][0]
    pbr = mat["pbrMetallicRoughness"]
    roles = {"BaseColor": pbr["baseColorTexture"], "ORM": pbr["metallicRoughnessTexture"],
             "NormalGL": mat["normalTexture"]}
    destination.mkdir(parents=True, exist_ok=True)
    result = {}
    for role, info in roles.items():
        image_index = doc["textures"][info["index"]]["source"]
        image = doc["images"][image_index]
        data = buffer_view_bytes(doc, bins, image["bufferView"])
        mime, dimensions = image_dimensions(data)
        extension = {"image/jpeg": ".jpg", "image/png": ".png"}[mime]
        output = destination / ("T_" + prefix + "_" + role + extension)
        if output.exists() and output.read_bytes() != data:
            raise FileExistsError(f"Refusing to replace different texture bytes: {output}")
        output.write_bytes(data)
        result[role] = {"path": str(output), "dimensions": dimensions,
                        "sha256": hashlib.sha256(data).hexdigest(), "source_image_index": image_index}
    (destination / "texture-source.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    if not args.prefix.isalnum():
        parser.error("prefix must contain only letters and digits")
    print(json.dumps(extract(project_path(args.source, "source"),
                             project_path(args.destination, "destination"), args.prefix)))
