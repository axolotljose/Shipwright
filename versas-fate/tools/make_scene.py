"""
make_scene.py - generates the "Versa's Vine Forest" scene, room, collision,
vertex and display-list resources as XML.

Run:  python tools/make_scene.py

Everything it writes goes into mod_src/ and is packed verbatim by
build_versas_fate.py. The XML is the same dialect SoH's own XML factories read
(soh/soh/resource/importer/SceneFactory.cpp and friends), which is why this mod
needs no Blender, no ZAPD and no ROM: the scene is plain text that the engine
parses at runtime.

    mod_src/scenes/shared/versa_scene/versa_scene      <- scene header
    mod_src/scenes/shared/versa_scene/versa_room_0     <- the one room
    mod_src/scenes/shared/versa_scene/versa_collision  <- collision header
    mod_src/objects/versas_fate/versa_room_0_vtx_*     <- vertex buffers
    mod_src/objects/versas_fate/versa_room_0_dl_*      <- display lists

Layout (units are OoT units; 100 units = 1 metre):

        z = +2500  +------------------------------------+
                   |  A  ENTRY CLEARING (moss, canopy)  |   spawn point,
                   |                                    |   Kokiri kids,
        z = +1300  |                                    |   Deku Babas
                   +--------------  vine wall  ---------+
                   |  B  PUZZLE GROVE (moss, canopy)    |   push block +
                   |                                    |   floor switch,
                   |        [block] [switch]            |   eye switch up
        z = -500   +--------------  bark gate  ----------+   high, 2 chests
                   |                                    |
                   |  C  VERSA'S HOLLOW (stone, torches)|   Gohma, 2 big
                   |             (o)                    |   babas, 4 pillars
        z = -2300  +------------------------------------+
                  x = -1400                        x = +1400

Puzzle logic (vanilla engine, no C++ needed):
  * Floor switch flag 0x0A -> chest 0x3020 (En_Box type 3 "falls when switch
    set", switch flag in its rotation.z) drops out of the canopy.
  * Eye switch flag 0x0B -> chest 0x37C1 drops in the north-west alcove.

Room/collision data is intentionally flat and axis aligned. Slopes, water boxes
and multi-room dungeon flow are described in docs/SCENE_AUTHORING.md.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD_SRC = os.path.join(ROOT, "mod_src")

SCENE_DIR = "scenes/shared/versa_scene"
OBJ_DIR = "objects/versas_fate"

# --------------------------------------------------------------------------
# layout constants
# --------------------------------------------------------------------------

X_MIN, X_MAX = -1400, 1400
Z_MIN, Z_MAX = -2300, 2500
FLOOR_TILE_X = 700
FLOOR_TILE_Z = 800
WALL_H = 500            # zones A and B
WALL_H_BOSS = 1000      # zone C
CANOPY_Y = 500
ZONE_C_Z = -500         # boss hollow starts here
ZONE_B_Z = 1300         # puzzle grove starts here

TEXEL_PER_REPEAT = 200  # world units per texture repeat

# --------------------------------------------------------------------------
# materials: how each texture is bound in the display lists
#   fmt/siz are the strings used by <SetTextureImage>, nfmt/nsiz the numeric
#   enums used by <LoadTextureBlock>, mask is the log2 of the texture size.
# --------------------------------------------------------------------------

MAT = {
    "moss":  dict(tex="textures/versas_fate/moss",  fmt="G_IM_FMT_I",  siz="G_IM_SIZ_4b", nfmt=4, nsiz=0, mask=6, xlu=False),
    "bark":  dict(tex="textures/versas_fate/bark",  fmt="G_IM_FMT_I",  siz="G_IM_SIZ_8b", nfmt=4, nsiz=1, mask=6, xlu=False),
    "stone": dict(tex="textures/versas_fate/stone", fmt="G_IM_FMT_I",  siz="G_IM_SIZ_8b", nfmt=4, nsiz=1, mask=6, xlu=False),
    "vine":  dict(tex="textures/versas_fate/vine",  fmt="G_IM_FMT_IA", siz="G_IM_SIZ_8b", nfmt=3, nsiz=1, mask=6, xlu=True),
    "leaf":  dict(tex="textures/versas_fate/leaf",  fmt="G_IM_FMT_IA", siz="G_IM_SIZ_4b", nfmt=3, nsiz=0, mask=6, xlu=True),
    "rune":  dict(tex="textures/versas_fate/rune",  fmt="G_IM_FMT_IA", siz="G_IM_SIZ_8b", nfmt=3, nsiz=1, mask=5, xlu=True),
}

TINT_DAY = (200, 210, 195)     # open canopy light
TINT_GROVE = (150, 175, 150)   # under the trees
TINT_DARK = (110, 130, 120)    # deep in the hollow
TINT_VINE = (140, 165, 130)

# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

class Quad(object):
    """One textured, double-triangle surface.

    verts are given in the order that should be CCW when viewed from the side
    the surface faces; `uv` is (u_repeats, v_repeats) over the whole quad.
    """

    def __init__(self, mat, verts, uv, tint, collide=False, surface=0):
        self.mat = mat
        self.verts = verts
        self.uv = uv
        self.tint = tint
        self.collide = collide
        self.surface = surface


def quad(mat, p0, p1, p2, p3, tint, u_repeat=1.0, v_repeat=1.0, collide=False, surface=0):
    return Quad(mat, (p0, p1, p2, p3), (u_repeat, v_repeat), tint, collide, surface)


def floor_grid():
    """The walkable floor, split into tiles so textures can repeat."""
    quads = []
    x = X_MIN
    while x < X_MAX:
        nx = min(x + FLOOR_TILE_X, X_MAX)
        z = Z_MIN
        while z < Z_MAX:
            nz = min(z + FLOOR_TILE_Z, Z_MAX)
            if z < ZONE_C_Z:
                mat, tint = "stone", TINT_DARK
            elif z < ZONE_B_Z:
                mat, tint = "moss", TINT_GROVE
            else:
                mat, tint = "moss", TINT_DAY
            # CCW seen from above -> normal points +Y
            quads.append(quad(mat,
                              (x, 0, z), (x, 0, nz), (nx, 0, nz), (nx, 0, z),
                              tint,
                              u_repeat=(nx - x) / float(TEXEL_PER_REPEAT),
                              v_repeat=(nz - z) / float(TEXEL_PER_REPEAT),
                              collide=True, surface=0))
            z = nz
        x = nx
    return quads


def wall_quads():
    """Perimeter walls, split into tiles along their length."""
    quads = []
    segments = []
    z = Z_MIN
    while z < Z_MAX:
        nz = min(z + FLOOR_TILE_Z, Z_MAX)
        segments.append((z, nz))
        z = nz

    for (z0, z1) in segments:
        h = WALL_H_BOSS if z1 <= ZONE_C_Z else WALL_H
        tint = TINT_DARK if z1 <= ZONE_C_Z else TINT_GROVE
        # west wall (faces +X)
        quads.append(quad("bark", (X_MIN, 0, z0), (X_MIN, h, z0), (X_MIN, h, z1), (X_MIN, 0, z1), tint,
                          u_repeat=(z1 - z0) / float(TEXEL_PER_REPEAT),
                          v_repeat=h / float(TEXEL_PER_REPEAT), collide=True, surface=1))
        # east wall (faces -X)
        quads.append(quad("bark", (X_MAX, 0, z1), (X_MAX, h, z1), (X_MAX, h, z0), (X_MAX, 0, z0), tint,
                          u_repeat=(z1 - z0) / float(TEXEL_PER_REPEAT),
                          v_repeat=h / float(TEXEL_PER_REPEAT), collide=True, surface=1))

    # south wall (faces -Z)
    x = X_MIN
    while x < X_MAX:
        nx = min(x + FLOOR_TILE_X, X_MAX)
        quads.append(quad("bark", (nx, 0, Z_MAX), (nx, WALL_H, Z_MAX), (x, WALL_H, Z_MAX), (x, 0, Z_MAX),
                          TINT_DAY, u_repeat=(nx - x) / float(TEXEL_PER_REPEAT),
                          v_repeat=WALL_H / float(TEXEL_PER_REPEAT), collide=True, surface=1))
        x = nx

    # north wall (faces +Z), taller, the boss hollow back wall
    x = X_MIN
    while x < X_MAX:
        nx = min(x + FLOOR_TILE_X, X_MAX)
        quads.append(quad("bark", (x, 0, Z_MIN), (x, WALL_H_BOSS, Z_MIN), (nx, WALL_H_BOSS, Z_MIN), (nx, 0, Z_MIN),
                          TINT_DARK, u_repeat=(nx - x) / float(TEXEL_PER_REPEAT),
                          v_repeat=WALL_H_BOSS / float(TEXEL_PER_REPEAT), collide=True, surface=1))
        x = nx
    return quads


def pillar_quads():
    """Four bark pillars in the hollow, each with a light on top later."""
    quads = []
    for (cx, cz) in ((-700, -1300), (700, -1300), (-700, -800), (700, -800)):
        s = 100
        h = WALL_H_BOSS - 200
        ring = [
            ((cx - s, 0, cz - s), (cx - s, 0, cz + s), (cx - s, h, cz + s), (cx - s, h, cz - s)),  # -X face
            ((cx + s, 0, cz + s), (cx + s, 0, cz - s), (cx + s, h, cz - s), (cx + s, h, cz + s)),  # +X face
            ((cx + s, 0, cz - s), (cx - s, 0, cz - s), (cx - s, h, cz - s), (cx + s, h, cz - s)),  # -Z face
            ((cx - s, 0, cz + s), (cx + s, 0, cz + s), (cx + s, h, cz + s), (cx - s, h, cz + s)),  # +Z face
        ]
        for v in ring:
            quads.append(quad("bark", v[0], v[1], v[2], v[3], TINT_DARK,
                              u_repeat=2 * s / float(TEXEL_PER_REPEAT),
                              v_repeat=h / float(TEXEL_PER_REPEAT), collide=True, surface=1))
    return quads


def canopy_quads():
    """Leaf canopy over zones A and B (translucent)."""
    quads = []
    x = X_MIN
    while x < X_MAX:
        nx = min(x + FLOOR_TILE_X * 2, X_MAX)
        z = ZONE_C_Z
        while z < Z_MAX:
            nz = min(z + FLOOR_TILE_Z * 2, Z_MAX)
            # faces -Y (down) so it is only visible from below
            quads.append(quad("leaf", (x, CANOPY_Y, nz), (x, CANOPY_Y, z), (nx, CANOPY_Y, z), (nx, CANOPY_Y, nz),
                              TINT_DAY, u_repeat=(nx - x) / float(TEXEL_PER_REPEAT),
                              v_repeat=(nz - z) / float(TEXEL_PER_REPEAT)))
            z = nz
        x = nx
    return quads


def vine_quads():
    """Hanging vine curtains on the walls and pillars (translucent)."""
    quads = []
    curtains = [
        # (x0, z0, facing) on the north wall
        (-1100, Z_MIN + 2), (-300, Z_MIN + 2), (500, Z_MIN + 2), (1200, Z_MIN + 2),
    ]
    for (cx, cz) in curtains:
        quads.append(quad("vine", (cx - 150, 0, cz), (cx - 150, 400, cz), (cx + 150, 400, cz), (cx + 150, 0, cz),
                          TINT_VINE, u_repeat=1.0, v_repeat=2.0))
    # vines down the west wall of the grove
    for cz in (200, 700, 1150):
        quads.append(quad("vine", (X_MIN + 2, 0, cz), (X_MIN + 2, 420, cz), (X_MIN + 2, 420, cz + 220),
                          (X_MIN + 2, 0, cz + 220), TINT_VINE, u_repeat=1.0, v_repeat=2.0))
    # vines on the two south-facing pillars
    for (cx, cz) in ((-700, -800), (700, -800)):
        quads.append(quad("vine", (cx - 100, 0, cz + 101), (cx - 100, 500, cz + 101), (cx + 100, 500, cz + 101),
                          (cx + 100, 0, cz + 101), TINT_VINE, u_repeat=1.0, v_repeat=2.5))
    return quads


def rune_quads():
    """The boss-arena sigil, on the floor facing up."""
    return [quad("rune", (-160, 2, -1960), (-160, 2, -1640), (160, 2, -1640), (160, 2, -1960),
                 TINT_DARK, u_repeat=1.0, v_repeat=1.0)]


def build_geometry():
    opa = []
    xlu = []
    coll = []
    for q in floor_grid() + wall_quads() + pillar_quads():
        (opa if not MAT[q.mat]["xlu"] else xlu).append(q)
        if q.collide:
            coll.append(q)
    for q in canopy_quads() + vine_quads() + rune_quads():
        (opa if not MAT[q.mat]["xlu"] else xlu).append(q)
    return opa, xlu, coll


# --------------------------------------------------------------------------
# display list XML
# --------------------------------------------------------------------------

DL_HEAD = """\
<DisplayList Version="0">
\t<SetCycleType G_CYC_1CYCLE="1" />
\t<SetCombineLERP A0="G_CCMUX_TEXEL0" B0="G_CCMUX_0" C0="G_CCMUX_SHADE" D0="G_CCMUX_0" A1="G_CCMUX_0" B1="G_CCMUX_0" C1="G_CCMUX_0" D1="G_CCMUX_TEXEL0" Aa0="G_ACMUX_TEXEL0" Ab0="G_ACMUX_0" Ac0="G_ACMUX_1" Ad0="G_ACMUX_0" Aa1="G_ACMUX_0" Ab1="G_ACMUX_0" Ac1="G_ACMUX_0" Ad1="G_ACMUX_1" />
\t<SetGeometryMode G_ZBUFFER="1" G_SHADE="1" G_CULL_BACK="1" G_FOG="1" />
\t<ClearGeometryMode G_LIGHTING="1" />
\t<Texture S="65535" T="65535" Level="0" Tile="0" On="1" />
"""

DL_OPA_TAIL = """\
\t<SetRenderMode Mode1="G_RM_AA_ZB_OPA_SURF" Mode2="G_RM_AA_ZB_OPA_SURF2" />
"""

DL_XLU_TAIL = """\
\t<SetRenderMode Mode1="G_RM_AA_ZB_XLU_SURF" Mode2="G_RM_AA_ZB_XLU_SURF2" />
"""


def emit_display_list(path, quads, vtx_path, xlu):
    """One display list per material group.

    Vertex slots: the engine loads vertices from the .vtx resource into a
    32 entry RSP buffer. `VertexBufferIndex` is the destination slot,
    `VertexOffset` the index into the .vtx resource, and the triangle
    commands reference destination slots. So a quad whose first vertex is
    number `i` goes to slot `i % 32` and its triangles use
    `i % 32 + 0/1/2` and `i % 32 + 0/2/3`. (This mirrors what SoH's own
    exporter writes for the shipped objects.)
    """
    lines = [DL_HEAD]
    lines.append(DL_XLU_TAIL if xlu else DL_OPA_TAIL)

    by_mat = {}
    for q in quads:
        by_mat.setdefault(q.mat, []).append(q)

    for mat_name in sorted(by_mat):
        m = MAT[mat_name]
        group = by_mat[mat_name]
        lines.append('\t<LoadTextureBlock Path="%s" Format="%d" Size="%d" Width="64" Height="64" MaskS="%d" '
                     'MaskT="%d" ShiftS="0" ShiftT="0" CMS_TXWrap="1" CMT_TXWrap="1" />\n' %
                     (m["tex"], m["nfmt"], m["nsiz"], m["mask"], m["mask"]))
        for qi, q in enumerate(group):
            slot = (qi * 4) % 32
            lines.append('\t<LoadVertices Path="%s" Count="4" VertexBufferIndex="%d" VertexOffset="%d" />\n' %
                         (vtx_path, slot, qi * 4))
            lines.append('\t<Triangles2 V00="%d" V01="%d" V02="%d" Flag0="0" V10="%d" V11="%d" V12="%d" '
                         'Flag1="0" />\n' % (slot, slot + 1, slot + 2, slot, slot + 2, slot + 3))
    lines.append('\t<EndDisplayList />\n</DisplayList>\n')
    write(path, "".join(lines))


def emit_vertex_buffer(path, quads):
    lines = ['<Vertex Version="0">\n']
    for q in quads:
        u_rep, v_rep = q.uv
        # one full texture repeat = size * 32 in the 10.5 fixed point texel format
        u_max = int(u_rep * 64 * 32)
        v_max = int(v_rep * 64 * 32)
        u_max = min(u_max, 32000)
        v_max = min(v_max, 32000)
        r, g, b = q.tint
        uv = ((0, 0), (u_max, 0), (u_max, v_max), (0, v_max))
        for i, (x, y, z) in enumerate(q.verts):
            s, t = uv[i]
            lines.append('\t<Vtx X="%d" Y="%d" Z="%d" S="%d" T="%d" R="%d" G="%d" B="%d" A="255" />\n' %
                         (round(x), round(y), round(z), s, t, r, g, b))
    lines.append('</Vertex>\n')
    write(path, "".join(lines))


# --------------------------------------------------------------------------
# collision XML
# --------------------------------------------------------------------------

def emit_collision(path, quads):
    verts = []
    polys = []
    for q in quads:
        base = len(verts)
        for v in q.verts:
            verts.append((round(v[0]), round(v[1]), round(v[2])))

        # two triangles per quad, keeping the quad's winding
        for (a, b, c) in ((0, 1, 2), (0, 2, 3)):
            p0, p1, p2 = (q.verts[a], q.verts[b], q.verts[c])
            n = normal(p0, p1, p2)
            dist = -round(n[0] * p0[0] + n[1] * p0[1] + n[2] * p0[2])
            polys.append((q.surface, base + a, base + b, base + c,
                          int(round(n[0] * 32767)), int(round(n[1] * 32767)), int(round(n[2] * 32767)),
                          dist))

    lines = ['<CollisionHeader Version="0" MinBoundsX="%d" MinBoundsY="0" MinBoundsZ="%d" MaxBoundsX="%d" '
             'MaxBoundsY="%d" MaxBoundsZ="%d">\n' % (X_MIN, Z_MIN, X_MAX, WALL_H_BOSS, Z_MAX)]
    for (x, y, z) in verts:
        lines.append('\t<Vertex X="%d" Y="%d" Z="%d" />\n' % (x, y, z))
    for (surface, a, b, c, nx, ny, nz, dist) in polys:
        lines.append('\t<Polygon Type="%d" VertexA="%d" VertexB="%d" VertexC="%d" NormalX="%d" NormalY="%d" '
                     'NormalZ="%d" Dist="%d" />\n' % (surface, a, b, c, nx, ny, nz, dist))
    # surface type 0: floor - camData index 0, normal dirt
    lines.append('\t<PolygonType Data1="0x0000" Data2="0x0000" />\n')
    # surface type 1: wall - same camera, wall-ish data
    lines.append('\t<PolygonType Data1="0x0000" Data2="0x0000" />\n')
    # one camera entry: standard "camera behind Link" setup for the whole room
    lines.append('\t<CameraData SType="1" NumData="1" CameraPosDataSeg="0" />\n')
    lines.append('\t<CameraPositionData PosX="0" PosY="0" PosZ="0" RotX="0" RotY="0" RotZ="0" FOV="60" JfifID="0" '
                 'Unknown="0" />\n')
    lines.append('</Collision>\n')
    write(path, "".join(lines))


def normal(p0, p1, p2):
    ax, ay, az = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    bx, by, bz = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
    nx, ny, nz = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length == 0.0:
        return (0.0, 1.0, 0.0)
    return (nx / length, ny / length, nz / length)


# --------------------------------------------------------------------------
# actors
# --------------------------------------------------------------------------

# Actor ids from soh/include/tables/actor_table.h. Params are documented per
# line; see docs/SCENE_AUTHORING.md for the bit layouts.
ACTORS = [
    # --- zone A: entry clearing ------------------------------------------
    # En_Ko (Kokiri kid). params = (no-path marker << 8) | child type.
    dict(id=0x0163, pos=(300, 0, 2000), rot=(0, 0x4000, 0), params=0xFF00 | 0, note="Kokiri kid, idles"),
    dict(id=0x0163, pos=(-350, 0, 2150), rot=(0, 0x9000, 0), params=0xFF00 | 1, note="Kokiri kid, idles"),
    dict(id=0x0163, pos=(0, 0, 1650), rot=(0, 0xC000, 0), params=0xFF00 | 2, note="Kokiri kid, idles"),
    # En_Dekubaba. params 0 = normal, 1 = big.
    dict(id=0x0055, pos=(-800, 0, 1550), rot=(0, 0, 0), params=0, note="Deku Baba"),
    dict(id=0x0055, pos=(850, 0, 1450), rot=(0, 0, 0), params=0, note="Deku Baba"),

    # --- zone B: the puzzle grove ----------------------------------------
    # Obj_Oshihiki (push block). params low nibble: 0 = PUSHBLOCK_SMALL_START_ON
    dict(id=0x00FF, pos=(-250, 0, 450), rot=(0, 0, 0), params=0, note="push block"),
    # Obj_Switch. params = (flag << 8) | (subtype << 4) | type(0=floor)
    dict(id=0x012A, pos=(150, 0, 300), rot=(0, 0, 0), params=(0x0A << 8) | 0, note="floor switch 1 -> flag 0x0A"),
    # En_Box. params = (type << 12) | (item << 5) | treasure flag; rot.z = switch flag
    dict(id=0x000A, pos=(150, 0, 250), rot=(0, 0, 0x0A), params=(3 << 12) | (0x01 << 5) | 0x00,
         note="chest 1: falls when 0x0A set (5 bombs)"),
    # Obj_Switch, eye type (2) high on the east wall -> flag 0x0B
    dict(id=0x012A, pos=(1200, 330, 700), rot=(0, 0x9000, 0), params=(0x0B << 8) | (0 << 4) | 2,
         note="eye switch 2 -> flag 0x0B"),
    dict(id=0x000A, pos=(-1150, 0, 250), rot=(0, 0, 0x0B), params=(3 << 12) | (0x3E << 5) | 0x01,
         note="chest 2: falls when 0x0B set (heart piece)"),
    # En_Dekunuts. params bits 8-15 = shots per round, low byte 0 = ground scrub
    dict(id=0x0060, pos=(-900, 0, -150), rot=(0, 0, 0), params=0x0200, note="Deku Scrub"),
    dict(id=0x0060, pos=(900, 0, -300), rot=(0, 0, 0), params=0x0300, note="Deku Scrub"),

    # --- zone C: Versa's Hollow ------------------------------------------
    dict(id=0x0028, pos=(0, 0, -1800), rot=(0, 0, 0), params=0, note="Boss: Gohma"),
    dict(id=0x0055, pos=(-800, 0, -650), rot=(0, 0, 0), params=1, note="Deku Baba (big)"),
    dict(id=0x0055, pos=(820, 0, -700), rot=(0, 0, 0), params=1, note="Deku Baba (big)"),
    # En_Light: decorative flames, params < 0x0F picks a colour profile
    dict(id=0x0008, pos=(-700, 400, -800), rot=(0, 0, 0), params=0, note="flame"),
    dict(id=0x0008, pos=(700, 400, -800), rot=(0, 0, 0), params=0, note="flame"),
    dict(id=0x0008, pos=(-700, 400, -1300), rot=(0, 0, 0), params=0, note="flame"),
    dict(id=0x0008, pos=(700, 400, -1300), rot=(0, 0, 0), params=0, note="flame"),
]

# Object ids from soh/include/tables/object_table.h
OBJECTS = [
    0x0001,  # OBJECT_GAMEPLAY_KEEP
    0x0002,  # OBJECT_GAMEPLAY_FIELD_KEEP
    0x0003,  # OBJECT_GAMEPLAY_DANGEON_KEEP (switch, push block)
    0x000E,  # OBJECT_BOX                     (chests)
    0x001C,  # OBJECT_GOMA                    (boss)
    0x0039,  # OBJECT_DEKUBABA
    0x004A,  # OBJECT_DEKUNUTS
    0x00C5,  # OBJECT_OS_ANIME                (Kokiri kids)
]

# Dynamic lights over the four flames in the hollow
LIGHTS = [
    (-700, 420, -800), (700, 420, -800), (-700, 420, -1300), (700, 420, -1300),
]


# --------------------------------------------------------------------------
# scene + room documents
# --------------------------------------------------------------------------

def emit_scene(path):
    lines = ['<Room Version="0">\n']

    # 0x00 SetStartPositionList - spawn 0 is the warp-in point
    lines.append('\t<SetStartPositionList>\n')
    lines.append('\t\t<StartPositionEntry Id="0" PosX="0" PosY="0" PosZ="2200" RotX="0" RotY="32768" RotZ="0" '
                 'Params="0" />\n')
    lines.append('\t</SetStartPositionList>\n')

    # 0x01 SetActorList
    lines.append('\t<SetActorList>\n')
    for a in ACTORS:
        lines.append('\t\t<ActorEntry Id="%d" PosX="%d" PosY="%d" PosZ="%d" RotX="%d" RotY="%d" RotZ="%d" '
                     'Params="%d" />\n' % (a["id"], a["pos"][0], a["pos"][1], a["pos"][2],
                                           a["rot"][0], a["rot"][1], a["rot"][2], a["params"]))
    lines.append('\t</SetActorList>\n')

    # 0x04 SetRoomList
    lines.append('\t<SetRoomList>\n')
    lines.append('\t\t<RoomEntry Path="%s/versa_room_0" VromStart="0" VromEnd="8192" />\n' % SCENE_DIR)
    lines.append('\t</SetRoomList>\n')

    # 0x05 SetWind
    lines.append('\t<SetWind WindWest="40" WindVertical="0" WindSouth="60" WindSpeed="10" />\n')

    # 0x06 SetEntranceList - entrance -> (room, spawn)
    lines.append('\t<SetEntranceList>\n')
    lines.append('\t\t<EntranceEntry Room="0" Spawn="0" />\n')
    lines.append('\t</SetEntranceList>\n')

    # 0x07 SetSpecialObjects
    lines.append('\t<SetSpecialObjects ElfMessage="0" GlobalObject="1" />\n')

    # 0x08 SetRoomBehavior - warp songs stay usable so the player can leave
    lines.append('\t<SetRoomBehavior GameplayFlags1="0" GameplayFlags2="0" />\n')

    # 0x0B SetObjectList
    lines.append('\t<SetObjectList>\n')
    for o in OBJECTS:
        lines.append('\t\t<ObjectEntry Id="%d" />\n' % o)
    lines.append('\t</SetObjectList>\n')

    # 0x0C SetLightList
    lines.append('\t<SetLightList>\n')
    for (x, y, z) in LIGHTS:
        lines.append('\t\t<LightInfo Type="0" X="%d" Y="%d" Z="%d" ColorR="255" ColorG="170" ColorB="90" '
                     'Radius="260" DrawGlow="1" />\n' % (x, y, z))
    lines.append('\t</SetLightList>\n')

    # 0x0F SetLightingSettings - four time-of-day variants, all dark and green
    lines.append('\t<SetLightingSettings>\n')
    settings = [
        # (ambient, light1 color, light1 dir, light2 color, light2 dir, fog color/near/far)
        ((28, 40, 34), (190, 210, 195), (0, 116, 60), (60, 70, 90), (0, -60, -40), (26, 40, 34), 900, 1400),
        ((34, 46, 38), (200, 215, 190), (10, 116, 55), (70, 80, 100), (0, -60, -40), (30, 44, 36), 900, 1400),
        ((22, 32, 28), (170, 190, 175), (-10, 116, 60), (60, 70, 90), (0, -60, -40), (20, 32, 28), 800, 1300),
        ((18, 26, 24), (150, 170, 160), (0, 116, 60), (50, 60, 80), (0, -60, -40), (16, 26, 24), 700, 1200),
    ]
    for (amb, l1c, l1d, l2c, l2d, fogc, fnear, ffar) in settings:
        lines.append('\t\t<LightingSetting AmbientColorR="%d" AmbientColorG="%d" AmbientColorB="%d" '
                     'Light1ColorR="%d" Light1ColorG="%d" Light1ColorB="%d" Light1DirX="%d" Light1DirY="%d" '
                     'Light1DirZ="%d" Light2ColorR="%d" Light2ColorG="%d" Light2ColorB="%d" Light2DirX="%d" '
                     'Light2DirY="%d" Light2DirZ="%d" FogColorR="%d" FogColorG="%d" FogColorB="%d" '
                     'FogNear="%d" FogFar="%d" />\n' % (
                         amb[0], amb[1], amb[2], l1c[0], l1c[1], l1c[2], l1d[0], l1d[1], l1d[2],
                         l2c[0], l2c[1], l2c[2], l2d[0], l2d[1], l2d[2],
                         fogc[0], fogc[1], fogc[2], fnear, ffar))
    lines.append('\t</SetLightingSettings>\n')

    # 0x10 SetTimeSettings - time stands still, it is always dusk in here
    lines.append('\t<SetTimeSettings Hour="0" Minute="0" TimeIncrement="0" />\n')

    # 0x11 SetSkyboxSettings - indoors: no sky, lighting only
    lines.append('\t<SetSkyboxSettings Unknown="0" SkyboxId="0" Weather="0" Indoors="1" />\n')

    # 0x12 SetSkyboxModifier
    lines.append('\t<SetSkyboxModifier SkyboxDisabled="1" SunMoonDisabled="1" />\n')

    # 0x13 SetExitList - none: the area has no physical exit, use a song or warp
    lines.append('\t<SetExitList>\n\t</SetExitList>\n')

    # 0x14 EndMarker
    lines.append('\t<EndMarker />\n')

    # 0x15 SetSoundSettings - SeqId 0x3E is NA_BGM_SARIA_THEME (Lost Woods):
    # that is the slot "Versa's Vine Forest" replaces in the SFX Editor.
    lines.append('\t<SetSoundSettings SeqId="62" NatureAmbienceId="0" Reverb="0" />\n')

    # 0x16 SetEchoSettings
    lines.append('\t<SetEchoSettings Echo="0" />\n')

    # 0x19 SetCameraSettings
    lines.append('\t<SetCameraSettings CameraMovement="0" WorldMapArea="0" />\n')

    lines.append('</Room>\n')
    write(path, "".join(lines))


def emit_room(path):
    lines = ['<Room Version="0">\n']
    lines.append('\t<SetMesh Data="0" MeshHeaderType="0" PolyNum="1">\n')
    lines.append('\t\t<Polygon PolyType="0" MeshOpa="%s/versa_room_0_dl_opa" MeshXlu="%s/versa_room_0_dl_xlu" />\n'
                 % (OBJ_DIR, OBJ_DIR))
    lines.append('\t</SetMesh>\n')
    lines.append('\t<SetCollisionHeader FileName="%s/versa_collision" />\n' % SCENE_DIR)
    lines.append('\t<EndMarker />\n')
    lines.append('</Room>\n')
    write(path, "".join(lines))


# --------------------------------------------------------------------------

def write(rel_path, text):
    full = os.path.join(MOD_SRC, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)
    return full


def pad_xml_sizes():
    """Rooms are loaded through the room list, whose VromStart/VromEnd only feed
    a buffer-size calculation. Keep the values in sync with the real file sizes
    so the numbers in the room list are not a lie."""
    room = os.path.join(MOD_SRC, SCENE_DIR, "versa_room_0")
    size = os.path.getsize(room)
    scene = os.path.join(MOD_SRC, SCENE_DIR, "versa_scene")
    with open(scene, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace('VromStart="0" VromEnd="8192"', 'VromStart="0" VromEnd="%d"' % max(size, 1))
    with open(scene, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    opa, xlu, coll = build_geometry()

    emit_scene(os.path.join(MOD_SRC, SCENE_DIR, "versa_scene"))
    emit_room(os.path.join(MOD_SRC, SCENE_DIR, "versa_room_0"))
    emit_collision(os.path.join(MOD_SRC, SCENE_DIR, "versa_collision"), coll)

    emit_vertex_buffer(os.path.join(MOD_SRC, OBJ_DIR, "versa_room_0_vtx_opa"), opa)
    emit_vertex_buffer(os.path.join(MOD_SRC, OBJ_DIR, "versa_room_0_vtx_xlu"), xlu)
    emit_display_list(os.path.join(MOD_SRC, OBJ_DIR, "versa_room_0_dl_opa"), opa,
                      "%s/versa_room_0_vtx_opa" % OBJ_DIR, xlu=False)
    emit_display_list(os.path.join(MOD_SRC, OBJ_DIR, "versa_room_0_dl_xlu"), xlu,
                      "%s/versa_room_0_vtx_xlu" % OBJ_DIR, xlu=True)
    pad_xml_sizes()

    print("scene  : %d opaque quads, %d translucent quads" % (len(opa), len(xlu)))
    print("coll   : %d quads -> %d triangles" % (len(coll), len(coll) * 2))
    print("actors : %d" % len(ACTORS))
    print("wrote  : mod_src/%s/{versa_scene,versa_room_0,versa_collision}" % SCENE_DIR)
    print("wrote  : mod_src/%s/versa_room_0_{vtx,dl}_{opa,xlu}" % OBJ_DIR)


if __name__ == "__main__":
    main()
