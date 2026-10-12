"""Deterministic storage helpers shared by the Blender skill tools."""

import gzip
import hashlib
import json
from pathlib import Path

MAX_JSON_BYTES = 64 * 1024 * 1024


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def compressed_json_path(path):
    path = Path(path)
    return path if path.suffix == '.gz' else Path(str(path) + '.gz')


def read_json(path):
    """Read JSON from PATH, falling back to the deterministic .gz variant."""
    path = Path(path)
    compressed = compressed_json_path(path)
    if path != compressed and path.exists() and compressed.exists():
        raise ValueError('Ambiguous JSON storage; remove the stale raw or gzip variant: ' + str(path))
    candidate = path if path.exists() else compressed
    if candidate.suffix == '.gz':
        with gzip.open(candidate, 'rb') as stream:
            payload = stream.read(MAX_JSON_BYTES + 1)
    else:
        if candidate.stat().st_size > MAX_JSON_BYTES:
            raise ValueError('JSON input exceeds the safety limit: ' + str(candidate))
        payload = candidate.read_bytes()
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError('JSON input exceeds the decompressed safety limit: ' + str(candidate))
    return json.loads(payload.decode('utf-8'))


def write_gzip_json(path, value):
    """Write compact UTF-8 JSON in a reproducible gzip container."""
    path = compressed_json_path(path)
    payload = (json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=9, mtime=0) as stream:
            stream.write(payload)
    temporary.replace(path)
    return path


def catalog_meaning_v3(catalog):
    """Schema-v3 meaning, including the now-retired raw-HTML audit hashes."""
    return {
        'source_version': catalog.get('source', {}).get('version'),
        'policy': catalog.get('policy'),
        'domains': catalog.get('domains'),
        'routes': catalog.get('routes'),
        'pages': catalog.get('pages'),
    }


def catalog_meaning(catalog):
    """Fields that affect routing, evidence selection, and SQLite discovery."""
    routes = []
    for original in catalog.get('routes') or []:
        route = dict(original)
        route['evidence'] = [
            {key: value for key, value in evidence.items() if key != 'html_sha256'}
            for evidence in route.get('evidence', [])
        ]
        routes.append(route)
    pages = [
        {key: value for key, value in page.items() if key != 'source_html_sha256'}
        for page in catalog.get('pages') or []
    ]
    return {
        'source_version': catalog.get('source', {}).get('version'),
        'policy': catalog.get('policy'),
        'domains': catalog.get('domains'),
        'routes': routes,
        'pages': pages,
    }


def catalog_fingerprint(catalog):
    payload = catalog_meaning_v3(catalog) if catalog.get('schema_version') == 3 else catalog_meaning(catalog)
    payload['semantic_corpus_sha256'] = catalog.get('source', {}).get('semantic_corpus_sha256')
    return sha256_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def valid_sha256(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(char in '0123456789abcdef' for char in value))


def validate_catalog(catalog):
    actual = catalog.get('catalog_sha256')
    if not valid_sha256(actual):
        raise ValueError('Catalog is missing catalog_sha256')
    compatible = catalog.get('compatible_catalog_sha256s', [])
    if (not isinstance(compatible, list) or not all(valid_sha256(item) for item in compatible) or
            len(compatible) != len(set(compatible)) or actual in compatible):
        raise ValueError('Catalog has invalid compatible fingerprints')
    if catalog.get('schema_version', 0) >= 3:
        expected = catalog_fingerprint(catalog)
    else:
        legacy = dict(catalog)
        legacy.pop('catalog_sha256', None)
        expected = sha256_bytes(json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode('utf-8'))
    if actual != expected:
        raise ValueError('Catalog fingerprint does not match its semantic content')
    return catalog


def semantic_corpus_fingerprint(db):
    """Hash model-visible corpus data independently of SQLite's physical layout."""
    checksum = hashlib.sha256()
    queries = [
        ('pages', 'SELECT path,title,body,category FROM pages ORDER BY path'),
        ('anchors', 'SELECT page,anchor,start,end FROM anchors ORDER BY page,anchor'),
        ('symbols', 'SELECT name,role,uri,display FROM symbols ORDER BY name,role,uri,display'),
        ('links', 'SELECT page,href,available FROM links ORDER BY page,href'),
    ]
    for label, query in queries:
        checksum.update((label + '\n').encode('ascii'))
        for row in db.execute(query):
            checksum.update(json.dumps(tuple(row), ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
            checksum.update(b'\n')
    return checksum.hexdigest()
