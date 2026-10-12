# SQLite API corpus and pre-query capability data

The installed skill uses `api/api.sqlite3` as its only detailed Blender API source. Raw HTML, images, scripts, Sphinx caches and source archives are intentionally not packaged. This reduces installation size without changing the model-facing discovery, lookup or evidence workflow.

Task use begins with the [catalog overview](catalog/overview.md), relevant domain and selected cards. Do not open SQLite or draft Blender code before reading that context. Blender knowledge recalled by the model is not admissible evidence.

## Provenance and coverage

The database was built from a local `blender_python_reference_5_2` Sphinx snapshot beginning at `index.html`:

- 2,192 indexed HTML pages and 33,696 anchor ranges.
- 26,775 root Sphinx inventory entries: 24,381 Python symbols, 2,161 document entries and 233 labels.
- HTML/JS identified API 5.2; root `objects.inv` identified project `Blender 5.2.1 LTS Python API`, version `5.2`.
- The source audit resolved all root inventory targets and local HTML fragments. The sole missing local target was the downloadable source ZIP linked from `index.html`, not an API page.
- External Manual, repository, extension and website links were not imported as task evidence.

These labels do not establish a release date, release status, installed executable or exact upstream build hash. Coverage, inventory headers and source byte/file counts are stored in the database metadata and are reported by `docs.py stats`.

## The layer read before SQLite

The generated catalog has 112 authored feature routes across 18 domains, plus a discovery card for every indexed page. `catalog/symbols.json.gz` exposes all root inventory entries without opening SQLite. These counts describe coverage of the supplied source and authored routing, not every possible Blender workflow.

Each authored route contains bilingual intent aliases, a source-grounded summary, choice criteria, explicit limits, source excerpts/hashes and exact next queries. `documented_route_runtime_unverified` means the source describes the feature; it does not establish an implemented recipe or tested CLI support.

Page cards retain titles, introductory excerpts where available, passage hashes and direct queries. `api_discovery_only` requires a detailed read before claiming behavior. `identifier_only` preserves a missing behavioral description rather than guessing from a name. Domain assignments and aliases are navigation aids, not additional Blender evidence.

From the skill directory:

```sh
python3 scripts/features.py overview
python3 scripts/features.py match "text strip shadow"
python3 scripts/features.py show sequencer-text-drop-shadow
python3 scripts/features.py pages video-audio --limit 35
python3 scripts/features.py symbols TextStrip
```

These commands read Markdown and compressed JSON and work without SQLite, Blender or network access. A match returns candidates to compare, not an automatic implementation verdict. If no route fits, inspect page cards. If the required fact is still absent, report `insufficient_skill_evidence` and stop dependent work.

## Detailed evidence storage and task reads

`api/api.sqlite3` stores page text, headings, anchor ranges, inventory symbols, links, search rows and coverage metadata. Repeated values are normalized behind SQL views. Text formatting is adapted for deterministic terminal display; the database contents are the packaged source of truth.

After selecting cards, create a plan and read the refs they supply:

```sh
python3 scripts/features.py plan --request "Text strip shadow" \
  --feature sequencer-text-drop-shadow --output /tmp/blender-plan.json
python3 scripts/docs.py read \
  bpy.types.TextStrip.html#bpy.types.TextStrip.use_shadow \
  --plan /tmp/blender-plan.json
```

`docs.py` records the canonical ref, passage hash and displayed line ranges. Continue pagination until every cited passage is complete. Reading an exact anchor can keep a passage small. Follow links exposed by completed reads, or select additional catalog cards before expanding scope. Search hits and identifier matches are discovery aids, not behavioral evidence.

FTS5 search is lexical and case-insensitive, with title weighting. Multiple terms default to AND; `--any` uses OR. `read` accepts an exact symbol, page or `page#anchor`; `related` reports main-article links and missing targets. Every Blender operation in a task script must still be bound to supporting evidence as described in [evidence-workflow.md](evidence-workflow.md).

Maintenance checks:

```sh
python3 scripts/docs.py stats
python3 scripts/docs.py verify
```

`verify` checks SQLite integrity, row/count invariants, FTS coverage, the semantic corpus fingerprint and the physical database fingerprint recorded by the catalog. It requires no HTML archive or manifest.

## Rebuild and review a replacement snapshot

Routine task use requires no raw HTML and no rebuild. A maintainer replacing the API snapshot must provide an external local Sphinx HTML tree and install `lxml`:

```sh
python3 scripts/build_corpus.py /absolute/path/new-api-html \
  --output /absolute/path/new-corpus
```

Use a new output directory for review. The builder refuses source symlinks and destinations nested inside the source. It traverses from `index.html`, parses articles and definition ranges, indexes root `objects.inv`, validates local targets and writes only `api.sqlite3`; it does not copy the authoring tree, evaluate scripts or deserialize caches.

Review version, provenance, database metadata and coverage differences before placing the database in a separate skill staging directory. Re-audit affected authored `catalog/routes-*.json` claims, then rebuild the pre-query catalog:

```sh
python3 scripts/build_catalog.py --skill /absolute/path/staging/blender-cli
```

The catalog builder validates database references, embeds excerpts and semantic hashes, then regenerates page cards, the compressed symbol inventory, domain files and catalog coverage. A physical SQLite layout change can remain compatible with existing plans when semantic content is identical. A semantic catalog or corpus change invalidates prior plans; recreate selection and reads rather than editing stored hashes.

Run database verification, skill validation and applicable tests against the staged replacement. Reference existence and matching hashes do not establish semantic accuracy: reviewers must compare authored summaries and choice criteria with the actual SQLite passages. Missing facts remain explicit gaps until supported material has been incorporated with provenance.
