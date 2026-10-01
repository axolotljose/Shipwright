# Applying the song-detection / warp hook

Everything in `VersasFate.o2r` works by dropping the archive into `mods/`.
The **only** thing an archive cannot do is teach the engine a *new song*, so
the mod ships one small C++ file that recognises the six ocarina notes of
"Versa's Lullaby" and warps the player to `ENTR_VERSAS_FATE` when they are
played. This document is the exact, minimal edit list.

Time needed: ~5 minutes plus one build.

---

## 0. What you need

* The Ship of Harkinian source you build (a.k.a. `soh/`): the folder that
  contains `soh/`, `soh/soh/`, `soh/include/`.
* A working build of that source, so you know your toolchain is fine before
  you change anything (see `docs/BUILDING.md` in the repo, or the
  [Ship of Harkinian build guide](https://github.com/HarbourMasters/Shipwright/blob/develop/docs/BUILDING.md)).

The three edits below are all that is required. `tools/apply_patch.py` does exactly these edits for you
(it copies the file, appends the two table lines, and can undo both):

```bat
python tools\apply_patch.py --soh-src "C:\path\to\Shipwright"
```

If you prefer to do it by hand, do the same three things.

---

## 1. Copy the hook file

```
versas-fate/patch/soh/soh/VersasFateWarp.cpp
        ->  <soh>/soh/soh/VersasFateWarp.cpp
```

That is the only file that is added. It is picked up automatically by the
glob in `soh/CMakeLists.txt` (`file(GLOB ... soh/soh/*.cpp)`), so no build
file edit is needed. CMake has to re-run to notice a new file - Visual Studio
and `cmake --build` do that automatically, but if in doubt delete
`build/CMakeCache.txt`'s generated project or just reconfigure.

What the file contains (so you can review it before trusting it):

* one `COND_HOOK(OnOcarinaNote, true, ...)` registration - the same
  game-interactor hook the Anchor dev branch uses to forward ocarina notes
  over the network (`soh/soh/Network/Anchor/HookHandlers.cpp:104`),
* a six-note cursor that only advances while
  `msgCtx.ocarinaAction == OCARINA_ACTION_FREE_PLAY`, ignores releases and
  heavily bent notes, and
* a warp that closes the ocarina textbox, plays the "song" fanfare and sets
  `nextEntranceIndex` / `transitionType` / `transitionTrigger`, which is the
  same sequence `soh/soh/Enhancements/QoL/PauseWarp.cpp` uses for the vanilla
  warp songs.

No vanilla song, message, save or audio code is modified.

## 2. Add the scene

`<soh>/soh/include/tables/scene_table.h` - append one line at the very end
(the file currently ends with `/* 0x6D */ DEFINE_SCENE(testroom_scene, ...)`):

```c
/* 0x6E */ DEFINE_SCENE(versa_scene, none, SCENE_VERSAS_FATE, SDC_DEFAULT, 0, 0)
```

* `versa_scene` is the resource path the engine loads:
  `scenes/shared/versa_scene/versa_scene` - the exact entry that is inside
  `VersasFate.o2r`. If you rename it here, rename it in the archive too.
* `none` is the repo's "no title card" marker (`z_scene_table.c:66`).
* `SCENE_VERSAS_FATE` becomes `0x6E`.

> **One side effect, and how to keep vanilla behaviour exactly:**
> `soh/include/z64scene.h:321` has
> `#define SCENE_UNUSED_6E SCENE_ID_MAX`. With the new scene, `SCENE_ID_MAX`
> moves from `0x6E` to `0x6F`, so the four *unused* entrance rows
> `ENTR_UNUSED_6E.._3` (`0x014..0x017`) would now point one past the last
> scene. Those entrances are never used by the game, but if you want them to
> keep their old value, change that line to `#define SCENE_UNUSED_6E 0x6E`
> while you are in there. Nothing else in the codebase depends on the old
> `SCENE_ID_MAX` value: it is only used as an array size
> (`gSceneTable[SCENE_ID_MAX]`, the Anchor scene arrays and
> `CrashHandlerExt.cpp`'s scene-name list), all of which simply grow by one.

Optional cosmetics: `soh/soh/CrashHandlerExt.cpp` has a
`std::array<const char*, SCENE_ID_MAX> sSceneIdToStrArray` used for crash
reports - add `"versa_scene"` at the end if you want readable names there.

## 3. Add the entrance

`<soh>/soh/include/tables/entrance_table.h` - append one line at the very end
(the file currently ends with `/* 0x613 */ DEFINE_ENTRANCE(ENTR_DESERT_COLOSSUS_8_3, ...)`;
the enum's `ENTR_MAX` is `0x614`, directly after it):

```c
/* 0x614 */ DEFINE_ENTRANCE(ENTR_VERSAS_FATE, SCENE_VERSAS_FATE, 0, false, true, TRANS_TYPE_FADE_WHITE, TRANS_TYPE_FADE_WHITE)
```

Argument order for the data macro is
`(enum, sceneId, spawn, continueBgm, displayTitleCard, endTransType, startTransType)`
(`soh/src/code/z_scene_table.c:32`). `spawn 0` is the spawn point defined by
`SetStartPositionList` in `versa_scene`, and `displayTitleCard` is `true` -
the same value every title-less vanilla scene uses (`SCENE_GROTTOS`,
`SCENE_SYOTES`, `SCENE_TESTROOM`); because the scene's title is `none` the card
has no text to draw, so nothing appears. If you decide to insert the entry
somewhere in the middle of the table instead of at the end, then
`VF_ENTRANCE_INDEX` in `VersasFateWarp.cpp` must be changed to match - the
default is `0x614`.

## 4. Build

Windows, from the `soh` folder (adjust to your IDE):

```bat
cmake --build build --config Release
```

* Visual Studio: open `soh.sln`, select `Release | x64`, Build.
* The first build after adding a file always takes a full recompile of the
  project that contains it (`soh`), which is a few minutes.

## 5. Test the hook

1. Copy `VersasFate.o2r` into `<your SoH folder>\mods\` (create it if
   missing - it sits next to `oot.o2r`).
2. Start the game, load a save with the ocarina, and press the ocarina
   button (default: **D-Pad Down** bound to the item, then **A**).
3. Play: **A, C-Up, C-Down, C-Left, C-Right, A**
   (`D4, D5, F4, B4, A4, D4`). Do not hold **R** - sharpened notes are wrong
   notes on purpose.
4. The screen should fade to white and you should load into the vine forest.

**Optional:** with the ocarina in your inventory, talk to **Saria** - in
Kokiri Forest early on, or in Sacred Forest Meadow where she gives you the
ocarina. The first time you do (once per session) she sings the melody so you
can hear it in the game's own instruments. Any other Kokiri in Kokiri Forest
does it too. It is a demonstration only: the song is never stored and the warp
does not depend on it.

If nothing happens:

| Symptom | Check |
|---|---|
| Crash at boot, "unknown scene" | The scene line is misplaced; it must be before the closing `};` of the enum, i.e. with the other `DEFINE_SCENE` lines. |
| Warp goes to a black screen / Doodongo's Cavern | The archive did not load. Check the log for `versa_scene`; confirm `mods/VersasFate.o2r` exists and is not zero bytes. |
| Song never triggers | You are probably not in free play (the hook ignores song demonstrations/checks). Also confirm you pressed six notes in the right order, with no extra notes in between. |
| The fanfare is not the mod's tune | That is expected: see `docs/CUSTOM_MUSIC.md` section 3 for the two-line change that lets the Audio Editor point a fanfare slot at "Versas Lullaby". |

## 6. Removing the hook

Delete `<soh>/soh/soh/VersasFateWarp.cpp` and the two added table lines, or run

```bat
python tools\apply_patch.py --soh-src "C:\path\to\Shipwright" --revert
```

The `.o2r` needs no change to be removed either - just delete it from `mods/`.
