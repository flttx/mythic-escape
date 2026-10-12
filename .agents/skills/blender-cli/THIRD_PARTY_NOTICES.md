# Third-party notices and source provenance

## License scope

The adjacent [MIT License](LICENSE) covers original project code and original documentation. It does **not** replace the licenses or copyright of third-party content. In particular, source excerpts embedded in otherwise original catalog files retain their upstream rights.

| Material | Location | Treatment |
| --- | --- | --- |
| Extracted Blender API text and inventory | `references/api/api.sqlite3` | Derived from the authoring snapshot; not relicensed as original project text |
| Source excerpts and inventory-derived cards | `references/catalog/catalog.json.gz`, `symbols.json.gz` | Upstream content remains subject to its own terms |
| Original helper code and editorial text | `scripts/`, `SKILL.md`, authored workflow descriptions | Project MIT terms, excluding incorporated third-party content |

## Blender documentation

The authoring HTML attributed copyright to **Blender Authors**. Its `documentation_options.js` identified version `5.2`; root `objects.inv` named `Blender 5.2.1 LTS Python API`. The authoring input was a local snapshot named `blender_python_reference_5_2`, not a freshly downloaded release verified by this project. Raw HTML, web assets and build caches are not packaged in the skill.

Coverage and provenance metadata are stored in `references/api/api.sqlite3` and can be inspected with `scripts/docs.py stats`. An exact upstream source commit/build hash is not established by the current record.

The upstream [Blender license page](https://www.blender.org/about/license/) describes GPL licensing and component-specific terms. The official repository's [API documentation configuration](https://github.com/blender/blender/blob/main/doc/python_api/conf.py) carries a `GPL-2.0-or-later` identifier. These are upstream provenance references, not a complete license determination for every file in this particular supplied HTML snapshot. Do not assign the Blender Manual's license to API documentation merely because both are hosted by Blender.

The authoring snapshot contained a cached `Blender 5.3 Manual` inventory, not the complete Manual. It is not merged into API search. Linked external pages and their licenses are not automatically included in this corpus.

## Redistribution review

The current provenance record does not establish complete redistribution terms for the derived API text. Before publicly redistributing the SQLite corpus or catalog excerpts:

1. Identify the exact source snapshot and applicable terms for API text.
2. Add the required license texts, attribution and source information for those components.
3. Confirm that distribution of the derived forms meets those terms; do not describe the whole corpus as MIT-licensed.
4. Record any deliberate source changes in provenance and rebuild derived data when needed.

Adding a project MIT License does not complete these upstream checks. This notice deliberately preserves the remaining provenance gap rather than claiming blanket redistribution clearance.

## Attribution and affiliation

Blender and its documentation are created by Blender's contributors. This repository is an independent community project and is not endorsed by or affiliated with the Blender Foundation.
