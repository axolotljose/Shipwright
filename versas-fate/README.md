# Versa's Fate

A Ship of Harkinian (SoH) mod that adds a new area, *Versa's Vine Forest*
(enemies, Kokiri, two puzzle props, treasure, a boss arena), three **vine pads**
that teleport you there from Kokiri Forest, Hyrule Field and Kakariko Village,
and the custom ocarina song *Versa's Lullaby* as a second way in - shipped as a
real `.o2r` archive plus one small, clearly delimited C++ file for the pads and
the song, which an archive cannot contain.

This folder is a complete, self-contained project: build the archive, copy it
into `mods/`, play. Everything here runs on Windows with a stock Python 3.9+
and no `pip install`.

## 0a. Windows: download a build that is already made (easiest)

GitHub builds this branch on `windows-latest` for every push, and publishes the
finished game - `soh.exe`, the assets, **and `mods/VersasFate.o2r` already
installed** - as a downloadable artifact. Nothing to install, no compiler, no
Visual Studio.

1. Open **https://github.com/axolotljose/Shipwright/actions/workflows/generate-builds.yml**
   (log in to GitHub - it is your own repo).
2. Click the newest run with a green tick, scroll to the bottom and download
   **`soh-windows`**.
3. Unzip it anywhere and run `soh.exe`. Pick your own ROM when asked. The mod
   is already in `mods/`.

No account-friendly mirror, if you would rather not log in:
**https://nightly.link/axolotljose/Shipwright/workflows/generate-builds.yml/arena/01a0f751-shipwright**

If the newest run is red, use 0b below instead: `build_it.bat` builds the same
thing on your own PC.

## 0b. Windows: the download you compile yourself

**Do not use GitHub's green "Code -> Download ZIP" button on this repo.** It
leaves the `libultraship/` and `torch/` submodules empty, so CMake stops during
configure, and the next build dies with
`MSBUILD : error MSB1009: ALL_BUILD.vcxproj does not exist`.

Grab this instead - it is the whole project *with* both dependencies inside
(the exact submodule revisions this branch pins):

**https://github.com/axolotljose/Shipwright/raw/arena/01a0f751-shipwright/versas-fate/download/Shipwright-VersasFate-with-dependencies.zip**

1. Download and extract it anywhere (e.g. `C:\Users\me\Downloads\VersasFate`).
   Keep it off OneDrive and out of `Program Files`.
2. Double-click `versas-fate\build_it.bat` in the extracted folder.
3. When it finishes it prints the path to `soh.exe` and has already copied
   `VersasFate.o2r` into `mods\` next to it. Run that `soh.exe`, pick your ROM,
   walk into Kokiri Forest (or Hyrule Field, or Kakariko Village) and step into
   the ring of vines that is drawn on the ground a few steps in front of you.

If you prefer git, `git clone --recurse-submodules` works too; the bat script
will also tell you if the dependencies are missing.

`build_it.bat` needs **Visual Studio 2022 with the "Desktop development with
C++" workload** (the free Build Tools are enough). It checks for it before it
starts and tells you exactly what to tick if it is missing - that check is
there because "The C compiler identification is unknown" is what CMake says
when the C++ workload is not installed. Everything CMake prints is also written
to `build_it.log` next to the script, so a failure can be read afterwards
instead of scrolling away.

> Reminder: the vine pads, the song and the Saria lesson live in the C++
> patch, so they only exist in the build produced by `build_it.bat`. Copying
> the `.o2r` into a different, unpatched SoH build gives you the Vine Forest,
> the music and the textures - but nothing that can take you there.

---

## 1. What is in the box

```
versas-fate/
  README.md                  this file
  VersasFate.o2r             the built mod archive (drop-in, 16 KB)
  tools/build_versas_fate.py packs mod_src/ -> VersasFate.o2r
  mod_src/                   the unpacked mod (this is what you edit)
    scenes/shared/versa_scene/    scene, room, collision (XML)
    objects/versas_fate/          display lists and vertex buffers (XML)
    textures/versas_fate/*.png    source textures ("<name>.<format>.png")
  music/*.seq                source sequences (3 placeholder tracks)
  tools/
    make_textures.py         regenerates the six textures from code
    make_scene.py            regenerates the scene/room/collision XML
    make_placeholder_music.py writes the three stand-in music/*.seq files
    audio_to_seq.py          mp3/wav -> monophonic .seq transcription
    pnglite.py               tiny dependency-free PNG reader/writer
  patch/
    APPLY.md                 the exact 3-edit C++ walkthrough
    soh/soh/VersasFateWarp.cpp      the hook file to copy in
  docs/
    CUSTOM_MUSIC.md          music: what an .o2r can and cannot do
    SCENE.md                 the scene layout, and how to change it
```

`mod_src/` is the source of truth for the archive. Everything in it is either
plain XML the engine parses at runtime, or a PNG named `<name>.<format>.png`
that `build_versas_fate.py` converts into a texture resource.

## 2. Quick start

```bat
cd versas-fate

REM 1. (optional) regenerate the assets from their generators
python tools\make_textures.py
python tools\make_scene.py
python tools\make_placeholder_music.py

REM 2. build the archive
python tools\build_versas_fate.py

REM 3. install it
copy VersasFate.o2r "C:\path\to\Ship of Harkinian\mods\VersasFate.o2r"
```

The mod archive is now installed and **auto-enabled**: SoH scans `mods/` on
boot and enables any valid `.o2r` it has not seen before, so there is no
checkbox to tick. If `mods/` does not exist yet, create it - it lives in the
same folder as `oot.o2r`.

The scene and the music work out of the box. Everything that *moves* you -
the vine pads and the song - needs the small C++ hook, because an archive
cannot add an object to a vanilla map or register a new ocarina song. That is
the one honest limit of the format, and section 5 tells you exactly what to do.

## 3. Installing and testing

**Install** - put the archive here:

```
<Ship of Harkinian>\
    oot.o2r
    mods\
        VersasFate.o2r      <-- this
```

Then start the game. Useful things to check:

| What to look at | Expected |
|---|---|
| Game log (`logs/` or the console) | No `Could not find sound font` / `Invalid Sequence` warnings |
| In-game audio editor (Enhancements → Audio Editor) | Three new entries: "Versas Vine Forest", "Versa Gohma", "Versas Lullaby" |
| Walking into Kokiri Forest, Hyrule Field or Kakariko Village | A ring of vines is drawn on the ground in front of you, and a notification says where you are |
| Standing in the middle of that ring (step off it first) | White fade into the vine forest |
| Playing A, C-Up, C-Down, C-Left, C-Right, A on the ocarina | Same warp |

**Getting there: the vine pads.** The pads cover the "no song required" case.
Each of the three areas has one, and it is placed the first time you walk into
that area while playing: ninety units (two steps) in front of wherever that
entrance drops Link, so it is always on open ground and always in view. Stand
in the middle of the ring and you travel; because the pad is right where you
come back to when you return from the forest, it deliberately ignores you until
you have taken a step off it and walked back in. The pads do not exist anywhere
else, do not touch the vanilla map data, and disappear again when you leave the
area.

**The lesson.** With the ocarina in your inventory, the first time you talk to
**Saria** (Kokiri Forest early on, or Sacred Forest Meadow where she hands you
the ocarina) she sings the melody for you, using the mod's own "Versas
Lullaby" sequence from the archive. Any other Kokiri in Kokiri Forest does the
same, for saves where Saria has moved on. Once per play session. This is a
demonstration, not an unlock: nothing is stored, and the song warps you before
and after it. If the archive is not installed the lesson falls back to the
vanilla Minuet jingle.

**Test the warp without the song.** If you applied the hook, you can also jump
straight into the scene from any save by adding a debug warp (Enhancements →
Debug → Warp) - the scene is the last entry in the list.

**Test the archive alone** (no C++ at all): an archive cannot teleport you, so
the way to see the scene without the hook is to temporarily point an existing
vanilla warp/song at it - or simply apply the hook, which is three edits.

## 4. What the scene contains

`docs/SCENE.md` describes the layout in detail; the short version:

* **One room**, 2800 x 4800 units (about 7 x 12 typical Link-heights), fully
  walled, floor and four torch-lit pillars, fogged and indoor-lit.
* **Spawn** at the northern end, facing the forest; a path leads south.
* **Enemies**: 2 Deku Babas, 2 Deku Scrubs, 4 torch flames, and **Boss Goma**
  waiting in the southern arena.
* **NPCs**: 3 Kokiri (`En_Ko`) near the entrance, one of them next to a chest.
* **Puzzle props**: one push block, one floor switch, one eye switch, two
  treasure chests (5 Bombs and a Heart Piece).
* **Lighting**: four lighting presets and four point lights on the pillars;
  the room is flagged indoors, so there is no day/night sky.
* **Music**: the room requests `NA_BGM_SARIA_THEME` (audio editor row
  "Lost Woods"), which is the slot you point at "Versas Vine Forest".

## 5. The one C++ file (vine pads + song + warp)

`patch/soh/soh/VersasFateWarp.cpp` is one file and does three things:

* **Draws the vine pads** in Kokiri Forest, Hyrule Field and Kakariko Village
  from the `OnPlayDrawEnd` hook - a flat mosaic of triangles laid on the
  ground in the port's "decal" render mode, the same trick SoH's own collision
  viewer uses, so no object, texture or actor has to exist for it.
* **Checks whether Link is standing on one** every frame (`OnGameFrameUpdate`)
  and hands over to the transition system with `ENTR_VERSAS_FATE`.
* **Listens on the existing `OnOcarinaNote` hook** for the six notes of the
  song, so playing it also warps - in order, in free play, without sharps.

Three edits, ~5 minutes: `patch/APPLY.md` has the exact lines and the build
command, and `patch/soh/soh/VersasFateWarp.cpp` is written to be read before
you trust it. Nothing vanilla is modified.

Song: **A, C-Up, C-Down, C-Left, C-Right, A** (D4 D5 F4 B4 A4 D4).

## 6. Music

Three tracks ship as placeholder `.seq` files (see `music/`), registered as
custom sequences in the archive:

| Archive entry | What it is |
|---|---|
| `custom/music/versasfate/Versas Vine Forest_bgm` | forest theme |
| `custom/music/versasfate/Versa Gohma_bgm` | boss theme |
| `custom/music/versasfate/Versas Lullaby_fanfare` | the melody (fanfare slot) |

Assign them once per config in the **Audio Editor** (the padlock button
unlocks it):

* Background Music → "Lost Woods" → **Versas Vine Forest**
* Battle Music → "Battle" → **Versa Gohma** (field scenes switch to the
  battle slot automatically when enemies are near, which is how the boss
  arena gets its own theme without any code)
* Fanfares → "Enter Zelda" → **Versas Lullaby** (after the one-line change in
  `patch/soh/soh/VersasFateWarp.cpp` described in `docs/CUSTOM_MUSIC.md`)

To use your own audio instead of the placeholders:

```bat
python tools\audio_to_seq.py "your_theme.mp3" -o music\versas_vine_forest.seq --bpm 96 --voices 3
python tools\build_versas_fate.py
```

`audio_to_seq.py` transcribes *monophonic* material: it slices the track into
eighth notes, finds the dominant pitch of each slice with a Goertzel filter
bank, and writes a sequence. It needs `ffmpeg` on PATH for anything that is
not a `.wav`. Read `docs/CUSTOM_MUSIC.md` before picking a source track - it
explains what transcribes well, and the high-fidelity alternative
(a one-sample custom sound font, which the engine supports but SoH's
`.ootrs` loader refuses to load from a music pack).

## 7. Honest limits

These are the things this mod **does not** pretend to do. They are stated here
so you can plan around them.

1. **Neither a vine pad nor a new ocarina song can live in an `.o2r`.** A
   pad is an object in a *vanilla* map, and a map's contents (its actor list)
   are decided by the game's own scene data - to add an entry, a mod would have
   to ship a copy of the whole scene, so this mod draws the pad and runs the
   "stand here" check from code instead. Song recognition is engine logic. Those
   two things are why the patch exists, and they are the *only* code in the mod.
2. **The pads are placed relative to the entrance, not at fixed coordinates.**
   Guessing world coordinates for "open floor" in three different maps, for
   every entrance into them, is how you end up with a pad inside a wall. They
   appear a couple of steps in front of wherever the entrance puts Link, which
   is guaranteed to be walkable ground, and they move with it.
3. **The song is recognised in free play only.** It deliberately ignores song
   demonstrations, ocarina-spot checks and the scarecrow recording so it can
   never fire while the game is playing notes at you.
4. **The switches are not wired to a door yet.** The floor switch sets flag
   `0x0A` and the eye switch `0x0B`; nothing consumes those flags in the
   shipped scene, because a door in a custom room has to be a *transition
   actor* (`Door_Shutter`, `0x2E`) and that list is empty right now.
   `docs/SCENE.md` has the exact XML for it. The two chests are ordinary
   player-opened rewards and work as they are.
5. **There is one room, and the boss arena is inside it.** There is no boss
   door, no boss-lock cutscene and no separate boss room; the camera in the
   arena is the standard dungeon camera, because `CAM_SET_BOSS_GOHMA` is not
   implemented in this fork (see `docs/SCENE.md`).
6. **No new models, animations or actors.** Enemies and NPCs are vanilla
   actors placed by id; the forest itself is textured quads generated by
   `tools/make_scene.py`. Importing a Blender mesh is possible (`DisplayList`
   and `Vertex` are text resources) but is not part of this project.
7. **No new text/messages.** Adding a textbox would mean shipping a `Text`
   resource and message ids; the mod deliberately avoids that.
8. **Custom music is note data, not audio.** A `.seq` plays the game's
   instruments. There is no supported path to stream an OGG/MP3 as
   background music from a `.o2r`; `docs/CUSTOM_MUSIC.md` explains exactly
   what is possible instead.
9. **Boss Goma without its vanilla scene.** It fights normally, but the boss
   health bar, boss music switch and the "boss defeated" cutscene that exist
   in Inside the Deku Tree come from scene/room behaviour and code paths that
   a custom room does not have. The arena is a *fight*, not a boss *encounter
   sequence*.

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Nothing new in the Audio Editor | The archive is not loading. Check `mods/VersasFate.o2r` exists and is not 0 bytes; check the log for `VersasFate`; make sure it is not inside a subfolder of `mods/`. |
| "Could not find sound font for sequence ..." | `music/*.seq` was replaced with a streamed sequence (`numFonts = -1`). Rebuild from the plain `.seq` files, or set `"font"` in `music/<name>.json`. |
| The forest is there but untextured/white | The texture resources did not make it into the archive. Run `python tools\make_textures.py` then `python tools\build_versas_fate.py`; texture entries must be named `<name>` (no format suffix) and match the `Path=` in the display list XML. |
| Scene loads, then you fall forever | Collision didn't load: check `scenes/shared/versa_scene/versa_collision` is in the archive and that the room XML's `SetCollisionHeader FileName=` matches it. |
| Wrong song triggers the warp | You are testing with the hook file from an older copy; the shipped one requires the exact six notes in free play. |
| `python tools\audio_to_seq.py` says ffmpeg was not found | Install ffmpeg (`winget install Gyan.FFmpeg`) or convert to `.wav` yourself first. |
| Archive is 16 KB but the game says it is corrupt | Something wrote a zero-byte file into the archive; `build_versas_fate.py` refuses to do that, so check you are using it and not a zip tool that stores directories. |

## 9. Rebuilding and editing

Everything is regenerable text; nothing here is a binary blob you have to
reverse-engineer:

| To change | Edit | Then run |
|---|---|---|
| Wall/floor layout, actor placement, lights, fog | `tools/make_scene.py` | `python tools\make_scene.py && python tools\build_versas_fate.py` |
| The look of a texture | the PNG in `mod_src/textures/` (keep the `<name>.<format>.png` name) | `python tools\build_versas_fate.py` |
| A melody | the note tables in `tools/make_placeholder_music.py`, or `tools/audio_to_seq.py` | `python tools\build_versas_fate.py` |
| The song/warp behaviour | `patch/soh/soh/VersasFateWarp.cpp` | rebuild SoH |

After any change, re-run `python tools\build_versas_fate.py` and copy the `.o2r`
over the old one; the game picks it up on the next boot.

## 10. Credit and licence

The scene, textures, music and hook in this folder were written for this mod.
Ship of Harkinian itself, and the actors it places, are the work of the
HarbourMasters project (see the `LICENSE` in the SoH repository).
