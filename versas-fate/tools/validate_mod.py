"""
validate_mod.py - checks the mod's resources the way the engine's own loaders will,
before the archive is packed.

Run:
    python tools/validate_mod.py                 # validates mod_src/
    python tools/validate_mod.py --o2r VersasFate.o2r

Why this exists
---------------
Every resource in an .o2r is parsed at runtime by a reader in the engine
(soh/soh/resource/importer/... and libultraship's src/fast/resource/factory/...).
Those readers are not forgiving:

  * XML is parsed with tinyxml2. A document that does not parse - a mismatched
    closing tag, an unquoted attribute - makes the resource load fail, and a
    failed load of something the game needs (a collision header, a display list)
    takes the game down with it.
  * Element and attribute names are matched literally. An unknown element is
    skipped silently, and an unknown attribute silently reads as 0, so a typo
    does not error - it just produces a resource that is quietly wrong.

So this script re-checks both things offline:

  1. every XML resource must parse with a strict XML parser (this catches the
     class of bug that crashed the mod on 2026-10-01: the collision header
     opened <CollisionHeader> and closed </Collision>);
  2. every element and attribute we emit must be one the engine's reader for
     that resource actually looks at (the tables below are extracted from those
     readers - see ELEMENT_ATTRIBUTES for the source of each one);
  3. every path one resource points at another with must exist in the archive;
  4. every index must be inside the array it indexes (vertex indices in a display
     list, vertex indices in a collision polygon, surface type index).

A resource that fails any of these is a bug that only shows up in game, so the
build refuses to package one.
"""

import argparse
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD_SRC = os.path.join(ROOT, "mod_src")

# --------------------------------------------------------------------------
# The vocabulary of the engine's XML readers.
#
# Element name -> the attributes its reader reads. Taken from:
#   Room / Set* / *Entry / *Setting      soh/soh/resource/importer/SceneFactory.cpp
#                                        soh/soh/resource/importer/scenecommand/*Factory.cpp
#   CollisionHeader / Vertex / Polygon /
#   PolygonType / CameraData /
#   CameraPositionData                   soh/soh/resource/importer/CollisionHeaderFactory.cpp
#   DisplayList / Vtx / Gfx elements     libultraship src/fast/resource/factory/DisplayListFactory.cpp
#   Vertex / Vtx                         libultraship src/fast/resource/factory/VertexFactory.cpp
# --------------------------------------------------------------------------

ELEMENT_ATTRIBUTES = {
    # --- containers (root elements; attributes are the container's own) -----
    "Room": {"Version"},
    "DisplayList": {"Version"},
    "Vertex": {"Version",                    # vertex buffer root
               "X", "Y", "Z"},               # collision vertex
    "CollisionHeader": {"Version", "MinBoundsX", "MinBoundsY", "MinBoundsZ",
                        "MaxBoundsX", "MaxBoundsY", "MaxBoundsZ"},
    "Sequence": {"SeqDataSize", "FontIndex"},

    # --- scene commands we emit --------------------------------------------
    "SetStartPositionList": set(),
    "StartPositionEntry": {"Id", "PosX", "PosY", "PosZ", "RotX", "RotY", "RotZ", "Params"},
    "SetActorList": set(),
    "ActorEntry": {"Id", "PosX", "PosY", "PosZ", "RotX", "RotY", "RotZ", "Params"},
    "SetRoomList": set(),
    "RoomEntry": {"Path", "VromStart", "VromEnd"},
    "SetWind": {"WindWest", "WindVertical", "WindSouth", "WindSpeed"},
    "SetEntranceList": set(),
    "EntranceEntry": {"Room", "Spawn"},
    "SetSpecialObjects": {"ElfMessage", "GlobalObject"},
    "SetRoomBehavior": {"GameplayFlags1", "GameplayFlags2"},
    "SetObjectList": set(),
    "ObjectEntry": {"Id"},
    "SetLightList": set(),
    "LightInfo": {"Type", "X", "Y", "Z", "ColorR", "ColorG", "ColorB", "Radius", "DrawGlow"},
    "SetLightingSettings": set(),
    "LightingSetting": {"AmbientColorR", "AmbientColorG", "AmbientColorB",
                        "Light1ColorR", "Light1ColorG", "Light1ColorB",
                        "Light1DirX", "Light1DirY", "Light1DirZ",
                        "Light2ColorR", "Light2ColorG", "Light2ColorB",
                        "Light2DirX", "Light2DirY", "Light2DirZ",
                        "FogColorR", "FogColorG", "FogColorB", "FogNear", "FogFar"},
    "SetTimeSettings": {"Hour", "Minute", "TimeIncrement"},
    "SetSkyboxSettings": {"Unknown", "SkyboxId", "Weather", "Indoors"},
    "SetSkyboxModifier": {"SkyboxDisabled", "SunMoonDisabled"},
    "SetExitList": set(),
    "ExitEntry": {"Id"},
    "EndMarker": set(),
    "SetSoundSettings": {"SeqId", "NatureAmbienceId", "Reverb"},
    "SetEchoSettings": {"Echo"},
    "SetCameraSettings": {"CameraMovement", "WorldMapArea"},
    "SetMesh": {"Data", "MeshHeaderType", "PolyNum"},
    "Polygon": {"PolyType", "MeshOpa", "MeshXlu",              # room mesh polygon
                "Type", "VertexA", "VertexB", "VertexC",        # collision polygon
                "NormalX", "NormalY", "NormalZ", "Dist"},
    "SetCollisionHeader": {"FileName"},

    # --- collision ----------------------------------------------------------
    "Vertex3s": set(),           # not used, kept for symmetry
    "Polygon3s": set(),
    "PolygonType": {"Data1", "Data2"},
    "CameraData": {"SType", "NumData", "CameraPosDataSeg"},
    "CameraPositionData": {"PosX", "PosY", "PosZ", "RotX", "RotY", "RotZ", "FOV", "JfifID", "Unknown"},

    # --- display lists ------------------------------------------------------
    "PipeSync": set(),
    "Texture": {"S", "T", "Level", "Tile", "On"},
    "SetPrimColor": {"M", "L", "R", "G", "B", "A"},
    "SetPrimDepth": {"Z", "DZ"},
    "SetFillColor": {"C"},
    "SetFogColor": {"R", "G", "B", "A"},
    "SetBlendColor": {"R", "G", "B", "A"},
    "SetEnvColor": {"R", "G", "B", "A"},
    "Grayscale": {"Enabled"},
    "SetGrayscaleColor": {"R", "G", "B", "A"},
    "SetDepthSource": {"Mode"},
    "SetAlphaCompare": {"Mode"},
    "SetAlphaDither": {"Type"},
    "SetColorDither": {"Type"},
    "SetCombineKey": {"Type"},
    "SetTextureFilter": {"Mode"},
    "SetTextureLOD": {"Mode"},
    "SetTextureDetail": {"Type"},
    "SetTexturePersp": {"Enable"},
    "PerspNormalize": {"S"},
    "FogPosition": {"Min", "Max"},
    "FogFactor": {"FM", "FO"},
    "NumLites": {"Lites"},
    "Segment": {"Seg", "Base"},
    "Matrix": {"Path", "Param"},
    "PopMatrix": {"Param"},
    "SetCycleType": {"G_CYC_1CYCLE", "G_CYC_2CYCLE", "G_CYC_COPY", "G_CYC_FILL"},
    "PipelineMode": {"G_PM_1PRIMITIVE", "G_PM_NPRIMITIVE"},
    "TileSync": set(),
    "LoadTile": {"T", "Uls", "Ult", "Lrs", "Lrt"},
    "SetTextureLUT": {"Mode"},
    "LoadTLUTCmd": {"Tile", "Count"},
    "SetCombineLERP": {"A0", "B0", "C0", "D0", "A1", "B1", "C1", "D1",
                       "Aa0", "Ab0", "Ac0", "Ad0", "Aa1", "Ab1", "Ac1", "Ad1"},
    "LoadSync": set(),
    "LoadBlock": {"Tile", "Uls", "Ult", "Lrs", "Dxt"},
    "LoadBlockWide": {"Tile", "Uls", "Ult", "Lrs", "Dxt"},
    "LoadTextureBlock": {"Path", "Format", "Size", "Width", "Height",
                         "MaskS", "MaskT", "ShiftS", "ShiftT",
                         "CMS_TXMirror", "CMS_TXNoMirror", "CMS_TXWrap", "CMS_TXClamp",
                         "CMT_TXMirror", "CMT_TXNoMirror", "CMT_TXWrap", "CMT_TXClamp"},
    "Triangle1": {"V00", "V01", "V02", "Flag0"},
    "Triangles2": {"V00", "V01", "V02", "Flag0", "V10", "V11", "V12", "Flag1"},
    "LoadVertices": {"Path", "Count", "VertexBufferIndex", "VertexOffset"},
    "SetTextureImage": {"Path", "Format", "Size", "Width"},
    "SetTile": {"Format", "Size", "Line", "TMem", "Tile", "Palette",
                "Cms0", "Cms1", "Cmt0", "Cmt1", "MaskS", "MaskT", "ShiftS", "ShiftT"},
    "SetTileSize": {"T", "Uls", "Ult", "Lrs", "Lrt"},
    "SetOtherMode": {"Cmd", "Sft", "Length"},
    "SetGeometryMode": {"G_ZBUFFER", "G_SHADE", "G_SHADING_SMOOTH", "G_CULL_FRONT", "G_CULL_BACK",
                        "G_CULL_BOTH", "G_FOG", "G_LIGHTING", "G_TEXTURE_GEN",
                        "G_TEXTURE_GEN_LINEAR", "G_CLIPPING"},
    "ClearGeometryMode": {"G_ZBUFFER", "G_SHADE", "G_SHADING_SMOOTH", "G_CULL_FRONT", "G_CULL_BACK",
                          "G_CULL_BOTH", "G_FOG", "G_LIGHTING", "G_TEXTURE_GEN",
                          "G_TEXTURE_GEN_LINEAR", "G_CLIPPING"},
    "SetRenderMode": {"Mode1", "Mode2"},
    "EndDisplayList": set(),

    # --- vertex buffers -----------------------------------------------------
    "Vtx": {"X", "Y", "Z", "S", "T", "R", "G", "B", "A"},
}

# Root element name -> what the resource is (the engine picks the reader from it).
ROOTS = {
    "Room": "scene or room",
    "DisplayList": "display list",
    "Vertex": "vertex buffer",
    "CollisionHeader": "collision header",
}


class Problems(object):
    def __init__(self):
        self.items = []
        self._seen = set()

    def add(self, message):
        if message in self._seen:
            return
        self._seen.add(message)
        self.items.append(message)

    def __bool__(self):
        return bool(self.items)


def parse_xml(path, problems):
    """Strict parse. A malformed document is a hard error, not a warning."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        problems.add("%s: XML does not parse (%s) - the engine would fail to load "
                     "this resource and crash if it is needed" % (path, exc))
        return None
    return tree


def check_vocabulary(path, tree, problems):
    root = tree.getroot()
    if root.tag not in ROOTS:
        problems.add("%s: root element <%s> is not a resource type the engine "
                     "knows (expected one of %s)" % (path, root.tag, ", ".join(sorted(ROOTS))))
        return root
    for element in root.iter():
        name = element.tag
        if name not in ELEMENT_ATTRIBUTES:
            problems.add("%s: element <%s> is not read by the engine's parser "
                         "(it would be silently ignored)" % (path, name))
            continue
        allowed = ELEMENT_ATTRIBUTES[name]
        for attr in element.attrib:
            if attr not in allowed:
                problems.add("%s: <%s> has attribute %s=, which the engine's parser "
                             "does not read (it would silently be 0)" % (path, name, attr))
    return root


def check_scene_references(path, root, entries, problems):
    """Paths a scene/room points at must exist in the archive."""
    for cmd in root:
        if cmd.tag == "SetRoomList":
            for room in cmd:
                ref = room.get("Path")
                if ref and ref not in entries:
                    problems.add("%s: <RoomEntry Path=\"%s\"> but no such resource in the archive"
                                 % (path, ref))
        elif cmd.tag == "SetCollisionHeader":
            ref = cmd.get("FileName")
            if ref and ref not in entries:
                problems.add("%s: <SetCollisionHeader FileName=\"%s\"> but no such resource "
                             "in the archive" % (path, ref))
        elif cmd.tag == "SetMesh":
            for polygon in cmd:
                for attr in ("MeshOpa", "MeshXlu"):
                    ref = polygon.get(attr)
                    if ref and ref not in entries:
                        problems.add("%s: <Polygon %s=\"%s\"> but no such resource in the archive"
                                     % (path, attr, ref))


def check_collision(root, problems, path):
    verts = [e for e in root if e.tag == "Vertex"]
    polys = [e for e in root if e.tag == "Polygon"]
    surface_types = [e for e in root if e.tag == "PolygonType"]
    for poly in polys:
        for attr in ("VertexA", "VertexB", "VertexC"):
            try:
                index = int(poly.get(attr))
            except (TypeError, ValueError):
                problems.add("%s: <Polygon %s=...> is missing or not a number" % (path, attr))
                continue
            if index >= len(verts):
                problems.add("%s: <Polygon %s=\"%d\"> but the collision header only has %d "
                             "vertices" % (path, attr, index, len(verts)))
        if surface_types:
            try:
                stype = int(poly.get("Type"))
            except (TypeError, ValueError):
                stype = 0
            if stype >= len(surface_types):
                problems.add("%s: <Polygon Type=\"%d\"> but there are only %d <PolygonType> "
                             "entries" % (path, stype, len(surface_types)))
    if not verts or not polys:
        problems.add("%s: collision header with %d vertices and %d polygons" % (path, len(verts), len(polys)))


def check_displaylist(root, entries, vertex_counts, problems, path):
    """Triangle indices must be inside a range a LoadVertices actually loaded."""
    loaded = set()
    for child in root:
        if child.tag == "LoadVertices":
            ref = child.get("Path")
            if ref not in entries:
                problems.add("%s: <LoadVertices Path=\"%s\"> but no such resource in the archive"
                             % (path, ref))
                continue
            count = int(child.get("Count", 0))
            base = int(child.get("VertexBufferIndex", 0))
            offset = int(child.get("VertexOffset", 0))
            available = vertex_counts.get(ref)
            if available is not None and offset + count > available:
                problems.add("%s: <LoadVertices Path=\"%s\" Count=\"%d\" VertexOffset=\"%d\"> reads "
                             "past the end of the vertex buffer (%d vertices)"
                             % (path, ref, count, offset, available))
            for i in range(count):
                loaded.add(base + i)
        elif child.tag in ("Triangles2", "Triangle1"):
            for attr in ("V00", "V01", "V02", "V10", "V11", "V12"):
                if child.get(attr) is None:
                    continue
                index = int(child.get(attr))
                if index not in loaded:
                    problems.add("%s: <%s %s=\"%d\"> uses a vertex that no preceding "
                                 "<LoadVertices> put in the buffer" % (path, child.tag, attr, index))


def source_files():
    """Every resource in mod_src/, keyed by the name it will have in the archive."""
    files = {}
    for dirpath, _dirnames, filenames in os.walk(MOD_SRC):
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, MOD_SRC).replace(os.sep, "/")
            if rel.endswith(".png"):
                stem, _, fmt = name[:-4].rpartition(".")
                rel = rel[: -len(fmt) - 5].rstrip(".")      # textures drop the format suffix
            files[rel] = full
    return files


def validate(files, report):
    """files: name -> path to read (or name -> bytes for the packed archive)."""
    problems = Problems()

    def read(name):
        data = files[name]
        if isinstance(data, bytes):
            return data
        with open(data, "rb") as handle:
            return handle.read()

    xml_names = [n for n in sorted(files) if b"<" == read(n)[:1]]

    # vertex buffers first: the display lists check their sizes
    vertex_counts = {}
    for name in xml_names:
        data = read(name)
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue                                   # reported below
        if root.tag == "Vertex":
            vertex_counts[name] = len([e for e in root if e.tag == "Vtx"])

    for name in xml_names:
        data = read(name)
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            problems.add("%s: XML does not parse (%s) - the engine would fail to load this "
                         "resource, and a failed load of a resource the game needs is a crash"
                         % (name, exc))
            continue

        if root.tag not in ROOTS:
            problems.add("%s: root element <%s> is not a resource type the engine knows "
                         "(expected one of %s)" % (name, root.tag, ", ".join(sorted(ROOTS))))
            continue

        for element in root.iter():
            if element.tag not in ELEMENT_ATTRIBUTES:
                problems.add("%s: element <%s> is not read by the engine's parser "
                             "(it would be silently ignored)" % (name, element.tag))
                continue
            for attr in element.attrib:
                if attr not in ELEMENT_ATTRIBUTES[element.tag]:
                    problems.add("%s: <%s> has attribute %s=, which the engine's parser does "
                                 "not read (it would silently be 0)" % (name, element.tag, attr))

        if root.tag == "Room":
            check_scene_references(name, root, files, problems)
        elif root.tag == "CollisionHeader":
            check_collision(root, problems, name)
        elif root.tag == "DisplayList":
            check_displaylist(root, files, vertex_counts, problems, name)

    report["problems"] = problems
    report["resources"] = len(files)
    report["xml"] = len(xml_names)
    return not problems


def main():
    parser = argparse.ArgumentParser(description="Validate the mod's resources before packing")
    parser.add_argument("--o2r", help="validate a packed .o2r instead of mod_src/")
    args = parser.parse_args()

    if args.o2r:
        with zipfile.ZipFile(args.o2r) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        label = args.o2r
    else:
        files = source_files()
        label = MOD_SRC

    report = {}
    ok = validate(files, report)

    print("validated %d resources (%d XML) in %s" % (report["resources"], report["xml"], label))
    if not ok:
        print("")
        for item in report["problems"].items:
            print("  FAIL  %s" % item)
        print("")
        print("%d problem(s) - not packaging a mod that would fail in game."
              % len(report["problems"].items))
        return 1

    print("all good: every XML parses, every element/attribute is one the engine reads,")
    print("every cross-reference exists and every index is in range.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
