"""Import the rigged/animated V5 Kraken FBX as a skeletal mesh + AnimSequences and assign the wet skin.

Source: ArtSource/Kraken/Rig/SK_Kraken_V5.fbx (built by ArtSource/Kraken/Rig/*). Writes a receipt
with bone/vertex counts and the imported animation assets.
"""
import json
import time

from ue_mcp import ROOT, UnrealMCP
from verify_boat_buoyancy import call, A

SM = 'editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools'
FOLDER = '/Game/MythicEscape/Chapters/Kraken/Art/Tripo/Kraken_V5/Rig'
MESH = FOLDER + '/SK_Kraken_V5'
MATERIAL = '/Game/MythicEscape/Chapters/Kraken/Art/Tripo/Kraken_V5/M_HeroKrakenV5_WetSkin'
SOURCE = ROOT / 'ArtSource/Kraken/Rig/SK_Kraken_V5.fbx'
CLIPS = ['Kraken_Emerge', 'Kraken_Idle', 'Kraken_StrikeA', 'Kraken_Submerge']


def ref(path):
    return {'refPath': path + '.' + path.rsplit('/', 1)[1]}


def main():
    m = UnrealMCP()
    receipt = {'source': str(SOURCE), 'folder': FOLDER}
    try:
        receipt['import'] = call(m, SM, 'import_file', folder_path=FOLDER, asset_name='SK_Kraken_V5',
                                 source_file=str(SOURCE), skeleton=None, import_materials=False,
                                 import_textures=False, import_animations=True, create_physics_asset=False)
    except Exception as exc:  # large imports can outlive the HTTP timeout; poll below
        receipt['import_request_error'] = str(exc)[:300]
    deadline = time.monotonic() + 1800
    while not call(m, A, 'exists', path=MESH):
        if time.monotonic() > deadline:
            raise RuntimeError('Skeletal mesh did not appear')
        time.sleep(10)
    assets = call(m, A, 'find_assets', folder_path=FOLDER, name='', asset_type='', recursive=True, tags=[])
    receipt['assets'] = assets
    mesh = ref(MESH)
    slots = call(m, SM, 'get_material_slots', mesh=mesh)
    receipt['material_slots'] = slots
    for slot in slots:
        name = slot if isinstance(slot, str) else slot.get('slotName', slot.get('name'))
        call(m, SM, 'set_material', mesh=mesh, slot_name=name, material=ref(MATERIAL))
    receipt.update(bones=len(call(m, SM, 'get_bone_names', mesh=mesh)),
                   vertices_lod0=call(m, SM, 'get_vertex_count', mesh=mesh, lod_index=0),
                   lods=call(m, SM, 'get_lod_count', mesh=mesh),
                   bounds=call(m, SM, 'get_bounds', mesh=mesh),
                   skeleton=call(m, SM, 'get_skeleton', mesh=mesh))
    receipt['animations'] = {c: [a for a in assets if a.rsplit('/', 1)[1].endswith(c)] for c in CLIPS}
    receipt['saved'] = call(m, A, 'save_assets', asset_paths=assets)
    out = ROOT / 'Artifacts/QA/kraken/kraken-rig-import.json'
    out.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=1)[:3000])


if __name__ == '__main__':
    main()
