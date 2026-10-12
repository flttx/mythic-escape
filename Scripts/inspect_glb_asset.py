#!/usr/bin/env python3
"""Read-only GLB 2.0 metadata audit for project-local source assets.

The report records structural metadata only. It never exports mesh data, embeds
image bytes, follows remote URLs, or makes artistic/UE import conclusions.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
GLB_MAGIC = b"glTF"
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
TRIANGLES, TRIANGLE_STRIP, TRIANGLE_FAN = 4, 5, 6


def project_path(value, purpose):
    path = Path(value).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as err:
        raise ValueError(f"{purpose} must remain inside the project root") from err
    return path


def parse_glb_bytes(data):
    if len(data) < 12:
        raise ValueError("truncated GLB header")
    magic, version, declared_length = struct.unpack_from("<4sII", data)
    if magic != GLB_MAGIC:
        raise ValueError("not a GLB file (missing glTF magic)")
    if version != 2:
        raise ValueError(f"unsupported GLB version {version}; expected 2")
    if declared_length != len(data):
        raise ValueError(f"GLB declared length {declared_length} does not match file length {len(data)}")
    chunks, offset = [], 12
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError("truncated GLB chunk header")
        length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        if length > len(data) - offset:
            raise ValueError("GLB chunk extends past declared file length")
        chunks.append((chunk_type, data[offset:offset + length]))
        offset += length
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise ValueError("GLB must begin with a JSON chunk")
    try:
        document = json.loads(chunks[0][1].decode("utf-8").rstrip(" \t\r\n\x00"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError("invalid GLB JSON chunk") from err
    if not isinstance(document, dict):
        raise ValueError("GLB JSON root must be an object")
    bin_chunks = [chunk for kind, chunk in chunks[1:] if kind == BIN_CHUNK]
    return data, document, bin_chunks, [{"type": chunk_name(kind), "byte_length": len(chunk)} for kind, chunk in chunks]


def parse_glb(path):
    return parse_glb_bytes(path.read_bytes())


def chunk_name(kind):
    return {JSON_CHUNK: "JSON", BIN_CHUNK: "BIN"}.get(kind, f"UNKNOWN_0x{kind:08X}")


def list_value(document, key):
    value = document.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"glTF {key} must be an array")
    return value


def index_value(items, index, label):
    if not isinstance(index, int) or index < 0 or index >= len(items):
        raise ValueError(f"invalid {label} index: {index!r}")
    return items[index]


def primitive_triangles(primitive, accessors):
    mode = primitive.get("mode", TRIANGLES)
    index = primitive.get("indices")
    if index is None:
        position = primitive.get("attributes", {}).get("POSITION")
        count = index_value(accessors, position, "POSITION accessor").get("count") if position is not None else None
    else:
        count = index_value(accessors, index, "indices accessor").get("count")
    if not isinstance(count, int):
        return None, "missing index/POSITION count"
    if mode == TRIANGLES:
        return count // 3, None if count % 3 == 0 else "triangle index count is not divisible by 3"
    if mode in (TRIANGLE_STRIP, TRIANGLE_FAN):
        return max(0, count - 2), None
    return None, f"primitive mode {mode} does not describe triangles"


def accessor_summary(accessor):
    return {key: accessor.get(key) for key in ("bufferView", "byteOffset", "componentType", "count", "type", "normalized", "min", "max") if key in accessor}


def mesh_summary(document):
    accessors = list_value(document, "accessors")
    meshes = list_value(document, "meshes")
    report, total_vertices, total_triangles = [], 0, 0
    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives", [])
        if not isinstance(primitives, list):
            raise ValueError(f"mesh {mesh_index} primitives must be an array")
        primitive_report = []
        for primitive_index, primitive in enumerate(primitives):
            attributes = primitive.get("attributes", {})
            if not isinstance(attributes, dict):
                raise ValueError(f"mesh {mesh_index} primitive {primitive_index} attributes must be an object")
            position = attributes.get("POSITION")
            vertices = None
            if position is not None:
                vertices = index_value(accessors, position, "POSITION accessor").get("count")
                if isinstance(vertices, int):
                    total_vertices += vertices
            triangles, note = primitive_triangles(primitive, accessors)
            if triangles is not None:
                total_triangles += triangles
            primitive_report.append({"index": primitive_index, "mode": primitive.get("mode", TRIANGLES),
                                     "vertex_count": vertices, "triangle_count": triangles,
                                     "triangle_note": note, "attributes": attributes,
                                     "indices_accessor": primitive.get("indices"),
                                     "material": primitive.get("material")})
        report.append({"index": mesh_index, "name": mesh.get("name"), "primitive_count": len(primitives),
                       "primitives": primitive_report})
    return {"mesh_count": len(meshes), "primitive_count": sum(item["primitive_count"] for item in report),
            "vertex_count_sum_per_primitive": total_vertices, "triangle_count_sum": total_triangles,
            "meshes": report, "accessor_count": len(accessors),
            "accessors": [accessor_summary(accessor) for accessor in accessors]}


def mat_mul(left, right):
    return [sum(left[row + 4 * k] * right[k + 4 * column] for k in range(4))
            for column in range(4) for row in range(4)]


def node_matrix(node):
    matrix = node.get("matrix")
    if matrix is not None:
        if not isinstance(matrix, list) or len(matrix) != 16 or not all(isinstance(value, (int, float)) for value in matrix):
            raise ValueError("node matrix must contain 16 numeric values")
        return matrix
    x, y, z, w = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    sx, sy, sz = node.get("scale", [1.0, 1.0, 1.0])
    tx, ty, tz = node.get("translation", [0.0, 0.0, 0.0])
    return [(1 - 2 * y * y - 2 * z * z) * sx, (2 * x * y + 2 * z * w) * sx, (2 * x * z - 2 * y * w) * sx, 0.0,
            (2 * x * y - 2 * z * w) * sy, (1 - 2 * x * x - 2 * z * z) * sy, (2 * y * z + 2 * x * w) * sy, 0.0,
            (2 * x * z + 2 * y * w) * sz, (2 * y * z - 2 * x * w) * sz, (1 - 2 * x * x - 2 * y * y) * sz, 0.0,
            tx, ty, tz, 1.0]


def transform_point(matrix, point):
    x, y, z = point
    transformed = [matrix[row] * x + matrix[row + 4] * y + matrix[row + 8] * z + matrix[row + 12] for row in range(4)]
    if transformed[3] and transformed[3] != 1:
        return [value / transformed[3] for value in transformed[:3]]
    return transformed[:3]


def scene_nodes(document):
    nodes = list_value(document, "nodes")
    scenes = list_value(document, "scenes")
    if scenes:
        scene_index = document.get("scene", 0)
        scene = index_value(scenes, scene_index, "scene")
        roots = scene.get("nodes", [])
    else:
        children = {child for node in nodes for child in node.get("children", [])}
        roots = [index for index in range(len(nodes)) if index not in children]
    result, visiting = [], set()
    identity = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]

    def visit(index, parent):
        if index in visiting:
            raise ValueError("node hierarchy contains a cycle")
        node = index_value(nodes, index, "node")
        visiting.add(index)
        world = mat_mul(parent, node_matrix(node))
        result.append((index, node, world))
        for child in node.get("children", []):
            visit(child, world)
        visiting.remove(index)

    for root in roots:
        visit(root, identity)
    return result


def bounds_summary(document):
    accessors, meshes = list_value(document, "accessors"), list_value(document, "meshes")
    limitations, points = [], []
    for node_index, node, matrix in scene_nodes(document):
        mesh_index = node.get("mesh")
        if mesh_index is None:
            continue
        mesh = index_value(meshes, mesh_index, "node mesh")
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            position = primitive.get("attributes", {}).get("POSITION")
            if position is None:
                limitations.append(f"node {node_index} mesh {mesh_index} primitive {primitive_index}: no POSITION accessor")
                continue
            accessor = index_value(accessors, position, "POSITION accessor")
            minimum, maximum = accessor.get("min"), accessor.get("max")
            if not (isinstance(minimum, list) and isinstance(maximum, list) and len(minimum) == len(maximum) == 3):
                limitations.append(f"node {node_index} mesh {mesh_index} primitive {primitive_index}: POSITION min/max unavailable")
                continue
            for x in (minimum[0], maximum[0]):
                for y in (minimum[1], maximum[1]):
                    for z in (minimum[2], maximum[2]):
                        points.append(transform_point(matrix, (x, y, z)))
    if not points:
        return {"computed": False, "reason": "no transformed POSITION accessor bounds available", "limitations": limitations}
    minimum = [min(point[axis] for point in points) for axis in range(3)]
    maximum = [max(point[axis] for point in points) for axis in range(3)]
    return {"computed": True, "min": minimum, "max": maximum,
            "dimensions": [maximum[axis] - minimum[axis] for axis in range(3)], "limitations": limitations}


def image_dimensions(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return "image/png", list(struct.unpack(">II", data[16:24]))
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            size = struct.unpack(">H", data[offset:offset + 2])[0]
            if size < 2 or offset + size > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF) and size >= 7:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                return "image/jpeg", [width, height]
            offset += size
    return None, None


def buffer_view_bytes(document, bin_chunks, view_index):
    views = list_value(document, "bufferViews")
    view = index_value(views, view_index, "bufferView")
    buffer_index = view.get("buffer", 0)
    if buffer_index != 0 or not bin_chunks:
        raise ValueError("image bufferView has no local GLB BIN chunk")
    start, length = view.get("byteOffset", 0), view.get("byteLength")
    if not isinstance(start, int) or not isinstance(length, int) or start < 0 or length < 0 or start + length > len(bin_chunks[0]):
        raise ValueError("image bufferView range is invalid")
    return bin_chunks[0][start:start + length]


def safe_external_image(path, uri):
    parsed = urlparse(uri)
    if parsed.scheme or parsed.netloc:
        return None, "external URI not read"
    candidate = (path.parent / unquote(parsed.path)).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None, "external image path outside project root was not read"
    if not candidate.is_file():
        return None, "external image file not found"
    return candidate.read_bytes(), None


def image_summary(document, bin_chunks, source_path):
    images = list_value(document, "images")
    report = []
    for index, image in enumerate(images):
        data, status = None, "not read"
        kind = "unknown"
        try:
            if "bufferView" in image:
                data, kind, status = buffer_view_bytes(document, bin_chunks, image["bufferView"]), "embedded", "read"
            elif isinstance(image.get("uri"), str) and image["uri"].startswith("data:"):
                header, encoded = image["uri"].split(",", 1)
                data, kind, status = base64.b64decode(encoded, validate=True), "data_uri", "read"
            elif isinstance(image.get("uri"), str):
                data, status = safe_external_image(source_path, image["uri"])
                kind = "external"
            else:
                status = "image has neither bufferView nor uri"
        except (ValueError, KeyError, IndexError, struct.error) as err:
            status = f"unreadable image: {type(err).__name__}"
        detected_mime, dimensions = image_dimensions(data) if data is not None else (None, None)
        report.append({"index": index, "name": image.get("name"), "kind": kind,
                       "declared_mime_type": image.get("mimeType"), "detected_mime_type": detected_mime,
                       "dimensions": dimensions, "read_status": status})
    return report


def material_summary(document, images):
    textures, materials = list_value(document, "textures"), list_value(document, "materials")
    image_refs, report = {"baseColor": [], "normal": [], "metallicRoughness": []}, []

    def texture_image(texture_info):
        if not isinstance(texture_info, dict) or "index" not in texture_info:
            return None
        texture = index_value(textures, texture_info["index"], "texture")
        source = texture.get("source")
        if source is not None:
            index_value(images, source, "image")
        return source

    for index, material in enumerate(materials):
        pbr = material.get("pbrMetallicRoughness", {})
        if not isinstance(pbr, dict):
            raise ValueError(f"material {index} pbrMetallicRoughness must be an object")
        refs = {"baseColor": texture_image(pbr.get("baseColorTexture")),
                "normal": texture_image(material.get("normalTexture")),
                "metallicRoughness": texture_image(pbr.get("metallicRoughnessTexture"))}
        for key, source in refs.items():
            if source is not None:
                image_refs[key].append(source)
        report.append({"index": index, "name": material.get("name"), "base_color_factor": pbr.get("baseColorFactor", [1, 1, 1, 1]),
                       "metallic_factor": pbr.get("metallicFactor", 1), "roughness_factor": pbr.get("roughnessFactor", 1),
                       "texture_image_indices": refs})
    return {"material_count": len(materials), "materials": report,
            "texture_image_reference_counts": {key: {str(value): values.count(value) for value in sorted(set(values))}
                                               for key, values in image_refs.items()}}


def asset_summary(document):
    asset = document.get("asset", {})
    if not isinstance(asset, dict):
        raise ValueError("glTF asset must be an object")
    # Do not copy extras: exporters can place source URLs or service metadata there.
    return {key: asset[key] for key in ("version", "minVersion", "generator", "copyright") if key in asset}


def audit(path):
    raw, document, bin_chunks, chunks = parse_glb(path)
    images = image_summary(document, bin_chunks, path)
    return {"schema": "mythic-glb-audit/1", "scope": "offline structural metadata only; not an artistic, rigging, UE import, or runtime quality verdict",
            "input": str(path.relative_to(ROOT)), "file": {"byte_length": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
            "glb": {"version": 2, "chunks": chunks}, "asset": asset_summary(document),
            "geometry": mesh_summary(document), "transformed_bounds": bounds_summary(document),
            "images": images, "materials": material_summary(document, images),
            "skins": {"count": len(list_value(document, "skins"))}, "animations": {"count": len(list_value(document, "animations"))}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_glb", help="Project-local .glb source asset")
    parser.add_argument("--output", required=True, help="Project-local audit JSON path")
    args = parser.parse_args()
    try:
        source, output = project_path(args.input_glb, "input"), project_path(args.output, "output")
        if source.suffix.lower() != ".glb":
            raise ValueError("input must use the .glb extension")
        if not source.is_file():
            raise ValueError("input GLB does not exist")
        report = audit(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output.relative_to(ROOT))
    except (OSError, ValueError, json.JSONDecodeError) as err:
        parser.error(str(err))


if __name__ == "__main__":
    main()
