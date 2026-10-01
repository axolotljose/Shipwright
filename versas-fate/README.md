# Versa's Fate

A Ship of Harkinian (SoH) mod that adds a custom ocarina song, *Versa's
Lullaby*, and a new area, *Versa's Vine Forest*, with enemies, Kokiri, two
puzzle props, treasure, and a boss arena - shipped as a real `.o2r` archive
plus one small, clearly delimited C++ file for the song itself.

This folder is a complete, self-contained project: build the archive, copy it
into `mods/`, play. Everything here runs on Windows with a stock Python 3.9+
and no `pip install`.

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

The scene and the music work out of the box. The *song* needs the small C++
hook, because an archive cannot register a new ocarina song - that is the one
honest limit of the format, and section 5 tells you exactly what to do.

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
| Playing the song | White fade into the vine forest |

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

## 5. The one C++ file (song detection + warp)

`patch/soh/soh/VersasFateWarp.cpp` is 160 lines and does two things: it
listens on the *existing* `OnOcarinaNote` game-interactor hook for the six
notes of the song, and it warps to `ENTR_VERSAS_FATE` when they are played in
order, in free play, without sharps.

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

1. **A brand new ocarina song cannot live in an `.o2r`.** Song recognition is
   engine logic, so it needs the file in `patch/`. That is why the patch
   exists, and it is the *only* code in the mod.
2. **The song is recognised in free play only.** It deliberately ignores song
   demonstrations, ocarina-spot checks and the scarecrow recording so it can
   never fire while the game is playing notes at you.
3. **The switches are not wired to a door yet.** The floor switch sets flag
   `0x0A` and the eye switch `0x0B`; nothing consumes those flags in the
   shipped scene, because a door in a custom room has to be a *transition
   actor* (`Door_Shutter`, `0x2E`) and that list is empty right now.
   `docs/SCENE.md` has the exact XML for it. The two chests are ordinary
   player-opened rewards and work as they are.
4. **There is one room, and the boss arena is inside it.** There is no boss
   door, no boss-lock cutscene and no separate boss room; the camera in the
   arena is the standard dungeon camera, because `CAM_SET_BOSS_GOHMA` is not
   implemented in this fork (see `docs/SCENE.md`).
5. **No new models, animations or actors.** Enemies and NPCs are vanilla
   actors placed by id; the forest itself is textured quads generated by
   `tools/make_scene.py`. Importing a Blender mesh is possible (`DisplayList`
   and `Vertex` are text resources) but is not part of this project.
6. **No new text/messages.** Adding a textbox would mean shipping a `Text`
   resource and message ids; the mod deliberately avoids that.
7. **Custom music is note data, not audio.** A `.seq` plays the game's
   instruments. There is no supported path to stream an OGG/MP3 as
   background music from a `.o2r`; `docs/CUSTOM_MUSIC.md` explains exactly
   what is possible instead.
8. **Boss Goma without its vanilla scene.** It fights normally, but the boss
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
