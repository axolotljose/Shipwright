# Versa's Vine Forest - the scene

The scene is **not** a Blender export. It is a small set of XML resources that
the engine reads directly, generated (and regenerated) by
`tools/make_scene.py`. That means you can change the level with a text editor,
and there is no asset pipeline to install.

```
mod_src/scenes/shared/versa_scene/versa_scene      scene header + commands
mod_src/scenes/shared/versa_scene/versa_room_0     the room: mesh + collision
mod_src/scenes/shared/versa_scene/versa_collision  collision header (quads)
mod_src/objects/versas_fate/versa_room_0_vtx_opa   opaque vertices
mod_src/objects/versas_fate/versa_room_0_vtx_xlu   translucent vertices
mod_src/objects/versas_fate/versa_room_0_dl_opa    opaque display list
mod_src/objects/versas_fate/versa_room_0_dl_xlu    translucent display list
```

Rebuild after any edit:

```bat
python tools\make_scene.py
python build_versas_fate.py
```

`make_scene.py` regenerates all seven files from a couple of tables at the top
of the file (wall segments, light settings, actor list, texture formats), so
the layout stays consistent between the mesh and the collision.

## Layout

The room is a flat arena, 2800 units east-west by 4800 units north-south,
with a perimeter wall. `TEXEL_PER_REPEAT = 200` makes each texture repeat
every 200 world units, so the 64x64 textures tile at a sensible world scale.

```
                     z = +2500  (far wall)
        +----------------------+
        |  spawn (0, 2200)     |   <- SetStartPositionList, rotY 0x8000
        |  Kokiri x3           |
        |  chest (bombs)       |   <- En_Box, GI_BOMBS_5
        |                      |
        |  Deku Baba   Baba    |
        |  push block          |   <- Obj_Oshihiki
        |  floor switch        |   <- Obj_Switch, switch flag 0x0A
        |                      |
        |  chest (heart piece) |   <- En_Box, GI_HEART_PIECE
        |  Deku Scrub  Scrub   |
        |                      |
        |  eye switch          |   <- Obj_Switch, switch flag 0x0B
        |                      |
        |   torches x4         |   <- En_Light, 4 point lights
        |   BOSS GOMA          |   <- Boss_Goma, southern arena
        +----------------------+
                     z = -2300  (boss arena)
```

* **Spawn**: `(0, 0, 2200)`, facing south (`rotY = 0x8000`). `SetEntranceList`
  maps room 0 / spawn 0, matching `spawn 0` in the entrance you add in
  `patch/APPLY.md`.
* **Actors**: 3 Kokiri (`En_Ko`, 0x163), 2 Deku Babas (0x55), 2 Deku Scrubs
  (`En_Dekunuts`, 0x60), 4 torch flames (`En_Light`, 0x08), 1 push block
  (`Obj_Oshihiki`, 0xFF), 2 switches (`Obj_Switch`, 0x12A), 2 chests
  (`En_Box`, 0x0A), 1 `Boss_Goma` (0x28).
* **Objects** requested by the room: GAMEPLAY_KEEP (1), FIELD_KEEP (2),
  DANGEON_KEEP (3), BOX (14), GOMA (28), DEKUBABA (57), DEKUNUTS (74),
  OS_ANIME (197).
* **Lighting**: four `LightingSetting` presets (calm, brighter, dim, storm -
  `SetTimeSettings` freezes time so they do not cycle) and four `LightInfo`
  points at the pillars. The room is flagged indoors with the skybox
  disabled.
* **Collision**: one quad per wall/floor tile, with the "floor" surface type
  so the camera behaves like inside a dungeon. There are no camera-setting
  volumes - see the boss note below.

## Changing the layout

Everything interesting is a table in `tools/make_scene.py`:

| Table | What it controls |
|---|---|
| `ACTORS` | every actor id, position, rotation and params |
| `LIGHTS` | the four point lights |
| `LIGHT_SETTINGS` | ambient/diffuse/fog per preset |
| `WALLS`, `FLOOR` | the tile grid that becomes both the mesh and the collision |

Positions are world units where 1 unit ~ 1 cm, y = 0 is the floor.

## Wiring the switches to doors (currently missing)

The floor switch sets switch flag `0x0A` and the eye switch sets `0x0B`, but
**no actor consumes those flags yet**, so today they are just switches. The
vanilla way to close the loop is a `Door_Shutter` (actor id `0x2E`), which is
a *transition actor*, not a normal actor, so it needs its own list in the
scene XML:

```xml
<SetTransitionActorList>
    <!-- FrontSideRoom/BackSideRoom: 0 because there is one room -->
    <!-- Params: (switchFlag) | (doorType << 6); doorType 1 = the Gohma
         shutter, whose object is GOMA (28) and is already requested -->
    <TransitionActorEntry FrontSideRoom="0" FrontSideEffects="0"
                          BackSideRoom="0" BackSideEffects="0"
                          Id="46" PosX="0" PosY="0" PosZ="0" RotY="0"
                          Params="74" />
</SetTransitionActorList>
```

`74` is `0x4A` = flag `0x0A` | door type `1 << 6`. Notes, all of them from the
actor's own source (`soh/src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c`):

* the switch flag is `params & 0x3F`; the door type is `(params >> 6) & 0xF`,
  and `sObjectInfo[]` at line 71 says which object each type needs - type `1`
  is `OBJECT_GOMA`, which the room already loads;
* bits 10 and up of the params are the entry's index in the transition actor
  list, so a second door needs `(1 << 10) | ...`. With one door the index is 0;
* transition actors are spawned by the engine, so do **not** also add them to
  `SetActorList`;
* the entry must be in the *room's* command list (`<Room>`/`<SetRoomList>`),
  because that is what `Scene_ExecuteCommands` walks.

The `SetTransitionActorList` element and its attributes are exactly what
`soh/soh/resource/importer/scenecommand/SetTransitionActorListFactory.cpp`
parses, so nothing else is needed.

## The boss arena

The southern half contains `Boss_Goma` surrounded by the four torch pillars.
Honest notes:

* **Camera.** `CAM_SET_BOSS_GOHMA` exists as an enum value but is not wired up
  in this fork (the boss never calls `Camera_ChangeSetting`), so the arena
  uses the normal dungeon camera. If you want a fixed arena camera, the
  supported vanilla mechanism is a `CameraSetting`/`CameraPosData` volume
  (`SetCameraSettings` in the scene, plus per-surface camera data in the
  collision), which `make_scene.py` currently leaves at the defaults.
* **Boss flow.** A custom room has no boss door, no boss music trigger, no
  health bar and no defeat cutscene. The fight itself works because
  `Boss_Goma` is an ordinary actor.
* **Music.** Field scenes switch to the *Battle Music* sequence when enemies
  are near, which is how the arena gets "Versa Gohma" without any code
  (`docs/CUSTOM_MUSIC.md`, section 3).

## Replacing the geometry with your own mesh

The mesh is plain XML, so any exporter that can write these three element
kinds can replace it:

* `<Vertex Version="0"><Vtx X= Y= Z= S= T= R= G= B= A=/>...</Vertex>` - the
  vertex buffer (`soh/assets/custom/objects/gameplay_keep/model.xml` in the
  SoH repo is a shipped example);
* `<DisplayList Version="0">` with `LoadTextureBlock`, `LoadVertices` and
  `Triangles2` commands - see `tools/make_scene.py` for the pattern, and note
  that `LoadVertices`'s `VertexBufferIndex` is the *destination* RSP slot, and
  that the RSP vertex buffer holds 64 vertices, so a mesh must reload
  vertices (the generated mesh reloads 4 at a time, which is always safe);
* the collision header, which is a list of quads with surface types.

That is the same shape SoH's own o2r uses, so exporting from Blender means
writing those three files, not learning a new format.
