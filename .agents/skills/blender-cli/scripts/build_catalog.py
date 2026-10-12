#!/usr/bin/env python3
"""Generate the pre-query capability layer from bundled evidence. Authoring only.

The generated JSON/Markdown can be read without SQLite, Blender, network or ML.
Domain assignment is navigation metadata, never a claim of task feasibility.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from storage import (catalog_fingerprint, catalog_meaning, read_json,
                     semantic_corpus_fingerprint, sha256_file, validate_catalog,
                     write_gzip_json)

SKILL = Path(__file__).resolve().parents[1]
DOMAIN_ROWS = [
    ('scene', 'Scenes, objects, collections and transforms', ['cảnh', 'đối tượng', 'vị trí', 'xoay', 'scene', 'object', 'collection', 'transform']),
    ('geometry', 'Mesh, BMesh and modifiers', ['lưới', 'hình học', 'bo cạnh', 'cắt khối', 'mesh', 'bmesh', 'modifier', 'topology']),
    ('geometry-nodes', 'Geometry Nodes, fields and instances', ['nút hình học', 'phân bố', 'nhân bản', 'geometry nodes', 'instance', 'field']),
    ('curves-volumes', 'Curves, 3D text, hair, point clouds and volumes', ['đường cong', 'chữ 3d', 'tóc', 'thể tích', 'curve', 'text geometry', 'hair', 'volume', 'grid']),
    ('sculpt-paint', 'Sculpting, brushes and painting', ['điêu khắc', 'tô màu', 'trọng số', 'sculpt', 'paint', 'brush', 'weight']),
    ('uv', 'UV maps, images and texture baking', ['trải uv', 'tọa độ uv', 'nướng texture', 'uv', 'unwrap', 'image', 'bake']),
    ('shading', 'Materials, shaders, textures and worlds', ['vật liệu', 'bề mặt', 'shader', 'material', 'texture', 'world']),
    ('lights-shadows', 'Lights, cameras and shadows', ['ánh sáng', 'đèn', 'đổ bóng', 'bóng', 'camera', 'light', 'shadow', 'reflection']),
    ('render', 'Rendering, passes, color and image output', ['kết xuất', 'render', 'pass', 'màu', 'png', 'output', 'color management']),
    ('compositor', 'Compositing, masks and image processing', ['hậu kỳ', 'ghép ảnh', 'khử nhiễu', 'compositing', 'mask', 'denoise', 'keying']),
    ('video-audio', 'Video editing, titles and audio', ['dựng phim', 'chữ video', 'âm thanh', 'video', 'sequencer', 'text strip', 'audio']),
    ('grease-pencil-freestyle', 'Grease Pencil, 2D strokes and Freestyle', ['vẽ 2d', 'nét vẽ', 'grease pencil', 'freestyle', 'line art', 'stroke']),
    ('tracking', 'Motion tracking and movie clips', ['bám chuyển động', 'giải camera', 'tracking', 'movie clip', 'camera solve']),
    ('animation-rigging', 'Keyframes, drivers, rigs and constraints', ['chuyển động', 'khung hình chính', 'xương', 'rig', 'animation', 'keyframe', 'driver', 'constraint']),
    ('simulation', 'Simulation, physics and caches', ['mô phỏng', 'vải', 'chất lỏng', 'khói', 'vật lý', 'simulation', 'physics', 'fluid', 'cloth', 'rigid body', 'particle']),
    ('files-assets', 'Files, import/export, libraries and assets', ['tệp', 'nhập', 'xuất', 'tài nguyên', 'file', 'import', 'export', 'library', 'asset']),
    ('integration-gpu', 'Python integration, math, GPU and UI', ['tích hợp', 'tiện ích', 'giao diện', 'toán', 'python', 'math', 'gpu', 'ui', 'registration']),
    ('api-guides', 'API guides, enums and source indices', ['tài liệu', 'hướng dẫn', 'enum', 'index', 'api reference', 'gotchas']),
]

# Audited storage-only migrations. Each entry pins both legacy physical inputs
# and the semantic corpus produced by the new layout; unrelated legacy catalogs
# must not gain plan compatibility merely because their route cards look alike.
LEGACY_STORAGE_MIGRATIONS = {
    'f7f35890ea31929ab58d2ff69438b5d05ff36762b1662916ef16b6b95d7785f8': {
        'database_sha256': '08d18853fc8c312299d19ff6d1962a0211dfe786c2c21297016230fe537f1089',
        'manifest_sha256': '7dcf879a5e4e643f8805eed01d434e1a0138e7ffb87b933c9b762b57a69a3581',
        'current_database_sha256': '72e8e6908468d884aec5676b0214f748404b707023b7a3865b5842366665da2d',
        'semantic_corpus_sha256': '2daab299f0787620df6c173282d4a6dd90114410c33af291fb6ea0c771bb6cb4',
    },
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_ref(db, ref):
    page, _, anchor = ref.partition('#')
    row = db.execute('SELECT body FROM pages WHERE path=?', (page,)).fetchone()
    if not row:
        raise ValueError('Missing page: ' + ref)
    body = row[0]
    if anchor:
        bounds = db.execute('SELECT start,end FROM anchors WHERE page=? AND anchor=?', (page, anchor)).fetchone()
        if not bounds:
            raise ValueError('Missing anchor: ' + ref)
        body = body[bounds[0]:bounds[1]]
    return body


def brief(body):
    """Select source prose after a class declaration, with no invented summary."""
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    class_i = next((i for i, line in enumerate(lines[:10]) if line.startswith('class bpy.types.')), None)
    if class_i is not None:
        line = lines[class_i + 1] if class_i + 1 < len(lines) else ''
        # A member name alone is not a capability description.
        if len(line.split()) < 3 or line.startswith(('classmethod ', 'base class', '##')):
            return '', 'identifier_only'
        return line[:500], 'source_description'
    useful = [line for line in lines if not line.startswith(('#', 'base class', '|', '-', 'class '))]
    first = ' '.join(useful[:2])[:500]
    return first, 'source_excerpt' if first else 'identifier_only'


def domains_for(page, category):
    if category in {'guides', 'indices', 'enum-items'}:
        return ['api-guides']
    name = page.removesuffix('.html').split('.')[-1]
    if page.startswith('bpy.ops.'):
        groups = {
            'scene': 'object collection transform scene world workspace ed'.split(),
            'geometry': 'mesh geometry lattice mball'.split(),
            'geometry-nodes': ['node'], 'curves-volumes': 'curve curves surface font pointcloud'.split(),
            'sculpt-paint': 'sculpt sculpt_curves paint paintcurve brush palette'.split(),
            'uv': 'uv image'.split(), 'shading': 'material texture'.split(),
            'lights-shadows': ['camera'], 'render': 'render cycles'.split(),
            'compositor': ['mask'], 'video-audio': 'sequencer sound'.split(),
            'grease-pencil-freestyle': 'gpencil grease_pencil'.split(), 'tracking': ['clip'],
            'animation-rigging': 'action anim armature pose poselib nla graph constraint marker'.split(),
            'simulation': 'rigidbody fluid cloth dpaint ptcache particle boid cachefile'.split(),
            'files-assets': 'wm file asset import_scene export_scene import_anim export_anim import_curve'.split(),
        }
        found = [key for key, names in groups.items() if name in names]
        return found or ['integration-gpu']
    if page.startswith(('bmesh',)):
        return ['geometry']
    if page.startswith(('freestyle',)):
        return ['grease-pencil-freestyle']
    if page.startswith('aud'):
        return ['video-audio']
    if not page.startswith('bpy.types.'):
        return ['integration-gpu']
    rules = [
        ('geometry-nodes', r'^(GeometryNode|FunctionNode|NodesModifier|NodeTreeInterface|NodeSocket|NodeLink|Nodes$)'),
        ('compositor', r'^(Compositor|Mask)'),
        ('shading', r'^(ShaderNode|TextureNode|Material|World|.*Texture)'),
        ('grease-pencil-freestyle', r'(GreasePencil|GPencil|ShaderFx|Freestyle|LineStyle|Annotation)'),
        ('video-audio', r'(Strip|Sequence|Sound|Speaker|TextEffect|FFmpeg|Aud)'),
        ('tracking', r'^(Movie|Track|CameraSolver|FollowTrack|ObjectSolver)'),
        ('animation-rigging', r'(Action|Anim|FCurve|FModifier|Keyframe|Keying|Driver|Nla|Bone|Armature|Pose|Constraint|ShapeKey|^Key$)'),
        ('simulation', r'(Fluid|Cloth|SoftBody|RigidBody|Particle|Boid|DynamicPaint|PointCache|Effector|FieldSettings|Collision)'),
        ('lights-shadows', r'^(Camera|.*Light|.*LightProbe)'),
        ('render', r'^(Render|Bake|ColorManaged|ImageFormat|AOV|Cryptomatte|SceneEEVEE|ViewLayer)'),
        ('curves-volumes', r'(Curve|Spline|MetaBall|Volume|PointCloud|TextCurve|VectorFont|Hair)'),
        ('sculpt-paint', r'(Sculpt|Paint|Brush|Palette|VertexGroup)'),
        ('uv', r'(UV|^Image|^UDIM)'),
        ('geometry', r'(Mesh|Modifier|Lattice|Attribute)'),
        ('files-assets', r'(Library|Asset|File|Packed|BlendData)'),
        ('scene', r'^(Object|Scene|Collection|LayerCollection|UnitSettings|TransformOrientation)'),
    ]
    for domain, pattern in rules:
        if re.search(pattern, name):
            return [domain]
    return ['integration-gpu']


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def compatible_fingerprints(previous, current):
    if not previous or catalog_meaning(previous) != catalog_meaning(current):
        return []
    same_semantic_corpus = (previous.get('schema_version', 0) >= 3 and
                            previous.get('source', {}).get('semantic_corpus_sha256') ==
                            current['source']['semantic_corpus_sha256'])
    migration = LEGACY_STORAGE_MIGRATIONS.get(previous.get('catalog_sha256'))
    verified_legacy_migration = bool(
        migration and
        previous.get('source', {}).get('database_sha256') == migration['database_sha256'] and
        previous.get('source', {}).get('manifest_sha256') == migration['manifest_sha256'] and
        current['source']['database_sha256'] == migration['current_database_sha256'] and
        current['source']['semantic_corpus_sha256'] == migration['semantic_corpus_sha256']
    )
    if not (same_semantic_corpus or verified_legacy_migration):
        return []
    candidates = [previous.get('catalog_sha256'), *previous.get('compatible_catalog_sha256s', [])]
    return list(dict.fromkeys(item for item in candidates if item and item != current['catalog_sha256']))


def build(skill=SKILL):
    root = skill / 'references/catalog'
    root.mkdir(exist_ok=True)
    try:
        previous_catalog = validate_catalog(read_json(root / 'catalog.json'))
    except FileNotFoundError:
        previous_catalog = None
    db_path = skill / 'references/api/api.sqlite3'
    db = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    domains = {key: {'id': key, 'label': label, 'aliases': aliases, 'routes': [], 'pages': []} for key, label, aliases in DOMAIN_ROWS}
    routes, seen = [], set()
    inputs = sorted(root.glob('routes-*.json'))
    if not inputs:
        raise ValueError('Missing authored routes-*.json inputs')
    for source in inputs:
        document = json.loads(source.read_text())
        for original in document['routes']:
            route = dict(original)
            rid = route['id']
            if rid in seen or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', rid):
                raise ValueError('Duplicate/invalid route ID: ' + rid)
            seen.add(rid)
            if route['domain'] not in domains:
                raise ValueError('Unknown domain: ' + route['domain'])
            for field in ['label_vi', 'label_en', 'summary', 'choose_when']:
                if not isinstance(route.get(field), str) or not route[field].strip():
                    raise ValueError(f'{rid}: missing text field {field}')
            for field in ['intent_aliases', 'api_refs', 'next_queries', 'evidence', 'do_not_assume']:
                if not isinstance(route.get(field), list):
                    raise ValueError(f'{rid}: {field} must be a list')
            if not route['evidence'] or not route['api_refs'] or not route['next_queries']:
                raise ValueError('Route lacks evidence/API entry point: ' + rid)
            evidence = []
            for fact in route['evidence']:
                body = read_ref(db, fact['ref'])
                if not fact.get('supports'):
                    raise ValueError('Empty source claim: ' + rid)
                excerpt = re.sub(r'\s+', ' ', body).strip()
                evidence.append({**fact, 'excerpt': excerpt[:1800], 'excerpt_truncated': len(excerpt) > 1800,
                                 'source_text_sha256': digest(body.encode())})
            route['evidence'] = evidence
            route['status'] = 'documented_route_runtime_unverified'
            route['authorship'] = 'Source-grounded editorial summary; Vietnamese aliases are translations, not extra Blender behavior.'
            for ref in set(route['api_refs'] + route['next_queries']):
                read_ref(db, ref)
            routes.append(route)
            domains[route['domain']]['routes'].append(rid)
    page_routes = defaultdict(set)
    for route in routes:
        for ref in route['api_refs'] + route['next_queries'] + [e['ref'] for e in route['evidence']]:
            page_routes[ref.split('#')[0]].add(route['domain'])
    pages = []
    for row in db.execute('SELECT path,title,body,category FROM pages ORDER BY path'):
        snippet, kind = brief(row['body'])
        assigned = sorted(set(domains_for(row['path'], row['category'])) | page_routes[row['path']])
        card = {'id': 'api:' + row['path'].removesuffix('.html'), 'page': row['path'], 'title': row['title'],
                'domains': assigned, 'source_excerpt': snippet, 'description_status': kind,
                'status': 'api_discovery_only', 'source_text_sha256': digest(row['body'].encode()),
                'next_queries': [row['path']]}
        pages.append(card)
        for domain in assigned:
            domains[domain]['pages'].append(card['id'])
    inventory_count = db.execute('SELECT count(*) FROM symbols').fetchone()[0]
    # All root symbols remain available as a source-derived compressed JSON inventory,
    # allowing names/roles to be discovered before opening the API database.
    symbols = [dict(row) for row in db.execute('SELECT name,role,uri FROM symbols ORDER BY name,role')]
    core = {'schema_version': 4, 'source': {'version': '5.2',
            'semantic_corpus_sha256': semantic_corpus_fingerprint(db),
            'database_sha256': sha256_file(db_path)},
            'policy': {'pretrained_blender_knowledge': 'forbidden_as_evidence',
                       'unknown_intent': 'insufficient_skill_evidence',
                       'api_discovery_only': 'Read source before making any behavior claim; an API name is not a workflow.'},
            'domains': list(domains.values()), 'routes': sorted(routes, key=lambda x: x['id']), 'pages': pages}
    core['catalog_sha256'] = catalog_fingerprint(core)
    compatible = compatible_fingerprints(previous_catalog, core)
    if compatible:
        core['compatible_catalog_sha256s'] = compatible
    write_gzip_json(root/'catalog.json', core)
    write_gzip_json(root/'symbols.json', {'source': 'root objects.inv only', 'symbols': symbols})
    (root/'catalog.json').unlink(missing_ok=True)
    (root/'symbols.json').unlink(missing_ok=True)
    report = {'schema_version': 4, 'authored_routes': len(routes), 'domains': len(domains), 'api_page_cards': len(pages),
              'source_html_pages': db.execute('SELECT count(*) FROM pages').fetchone()[0], 'inventory_entries': inventory_count,
              'mapped_pages': len({card['page'] for card in pages}), 'unmapped_pages': [],
              'cards_without_description': [card['id'] for card in pages if card['description_status']=='identifier_only'],
              'evidence_references': sum(len(r['evidence']) for r in routes),
              'coverage_meaning': 'All source pages/symbols are discoverable before SQLite. Authored routes are not every possible Blender workflow. Missing semantics remain explicit gaps.',
              'semantic_corpus_sha256': core['source']['semantic_corpus_sha256'],
              'catalog_sha256': core['catalog_sha256']}
    write_json(root/'coverage.json', report)
    overview = [
        '# Capability catalog before API lookup', '',
        'Read this entire page before opening SQLite. This catalog supplies Blender context to the agent; do not add capabilities, APIs, enums or workflows from pretrained Blender knowledge.', '',
        f'The catalog contains {len(routes)} source-backed routes, {len(pages)} source-page cards and {inventory_count} inventory entries. An API card is a discovery entry point, not proof of a documented workflow or working CLI implementation.', '',
        '| Domain | Search aliases (English / Vietnamese) | Authored routes | Source cards |', '|---|---|---|---|',
    ]
    for domain in domains.values():
        overview.append(f"| [{domain['label']}](domains/{domain['id']}.md) | {', '.join(domain['aliases'])} | {len(domain['routes'])} | {len(domain['pages'])} |")
    overview += ['', '## Selecting a route', '',
        '1. Match the request to the domains above using the supplied language and context. Do not guess API identifiers.',
        '2. Read the domain file and compare purpose, selection criteria and gaps. `features.py match` searches English/Vietnamese aliases using JSON only, without opening the database.',
        '3. Read selected routes with `features.py show ID` for source excerpts, limits and seed queries. Select multiple routes for combined tasks.',
        '4. If no route fits, inspect domain page cards (`features.py pages DOMAIN`) and select only behavior supported by source descriptions. Missing descriptions do not permit inferring behavior from names.',
        '5. If evidence is still insufficient, report `insufficient_skill_evidence`, identify the missing fact and request source material or clarification of the output. Do not substitute model memory.', '',
        '## Status values', '',
        '- `documented_route_runtime_unverified`: a source-backed description and query route; inspect the actual API/runtime before execution.',
        '- `api_discovery_only`: a source page/API exists, but this card is not an authored task route; read the source before proceeding.',
        '- `identifier_only`: introductory text does not sufficiently describe behavior. Preserve the gap; a class name is not evidence.', '',
        'Routes and cards derive from the bundled API corpus. Blender Manual and web content have not been added to this layer. The catalog does not establish background-mode support for every feature.',
    ]
    (root/'overview.md').write_text('\n'.join(overview)+'\n')
    directory = root/'domains'
    directory.mkdir(exist_ok=True)
    by_id = {r['id']: r for r in routes}
    for domain in domains.values():
        lines = [f"# {domain['label']}", '', 'Select by purpose and evidence below. Identify a route/source card before querying SQLite or proposing API identifiers.', '']
        for rid in domain['routes']:
            route = by_id[rid]
            lines += [f"## {route['label_en']} — `{rid}`", '', route['summary'], '',
                      f"Choose when: {route['choose_when']}", '', f"Search aliases: {', '.join(route['intent_aliases'])}", '',
                      'Evidence: ' + '; '.join(f"`{e['ref']}` — {e['supports']}" for e in route['evidence']), '',
                      'Read next: ' + ', '.join('`'+q+'`' for q in route['next_queries']), '']
            if route['do_not_assume']:
                lines += ['Limits: ' + ' '.join(route['do_not_assume']), '']
        lines += ['## Discover all source pages in this domain', '',
                  f"`python3 scripts/features.py pages {domain['id']}` lists {len(domain['pages'])} source cards with pagination. Each card retains its source name and description excerpt. Catalog discovery does not require SQLite.", '',
                  'Source pages remain discoverable even without an authored route. Read their descriptions/definitions before planning; do not supply missing behavior from model knowledge.', '']
        (directory/f"{domain['id']}.md").write_text('\n'.join(lines))
    db.close()
    print(json.dumps({k: v for k,v in report.items() if k!='cards_without_description'}, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, default=SKILL)
    build(parser.parse_args().skill.resolve())
