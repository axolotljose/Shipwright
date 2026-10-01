/**
 * VersasFateWarp.cpp
 * ==================
 *
 * The ONLY game-code change the "Versa's Fate" mod needs.
 *
 * Copy this file to:   <soh>/soh/soh/VersasFateWarp.cpp
 * (then append two lines to the scene/entrance tables - see patch/APPLY.md)
 *
 * It does exactly two things:
 *   1. listens to the notes the player plays on the ocarina (the vanilla
 *      engine only knows its own songs, so a mod's own song has to be
 *      recognised in code), and
 *   2. when the six-note melody of "Versa's Lullaby" has just been played,
 *      sends the player through a white fade into the entrance defined by
 *      ENTR_VERSAS_FATE - the entrance you add to
 *      soh/include/tables/entrance_table.h (see patch/APPLY.md).
 *
 * Everything else - the scene, the room, the collision, the textures, the
 * music, the actors, the puzzles, the boss - is data inside VersasFate.o2r
 * and is NOT touched here.
 *
 * Melody (N64 controller buttons; on keyboard the port's ocarina bindings):
 *
 *     A  ->  C-Up  ->  C-Down  ->  C-Left  ->  C-Right  ->  A
 *
 * which in engine pitch terms is D4, D5, F4, B4, A4, D4:
 *
 *     D4 = A button,  F4 = C-Down, A4 = C-Right, B4 = C-Left, D5 = C-Up.
 *
 * Hold R while pressing a note to sharpen it; "Versa's Lullaby" does not use
 * any sharpened notes, and a heavily bent note counts as a wrong note (the
 * same rule the vanilla song checker uses).
 *
 * How the detection works, and why it is not attached to the vanilla song
 * machinery: soh/src/code/code_800EC960.c already exposes an
 * `OnOcarinaNote(pitch, bendFreq, instrument)` hook that fires for every
 * ocarina note the player plays.  We keep a small cursor into our own note
 * table and walk it forward on every *new* pitch while `ocarinaAction` is
 * OCARINA_ACTION_FREE_PLAY (i.e. freestyle playing, never during a song
 * demonstration, the memory game or an ocarina-spot check).  Nothing here
 * touches `AudioOcarina_CheckSongs*`, so no vanilla song behaviour changes.
 *
 * Build: this file is picked up automatically by the glob in
 * soh/CMakeLists.txt, so it is enough to re-run CMake (or just build) after
 * copying it in.  See patch/APPLY.md for the full Windows walkthrough.
 */

#include "soh/ShipInit.hpp"
#include "soh/Enhancements/game-interactor/GameInteractor.h"

extern "C" {
#include "functions.h"
#include "macros.h"
#include "variables.h"
}

extern "C" PlayState* gPlayState;

/* ------------------------------------------------------------------------ *
 * Configuration
 * ------------------------------------------------------------------------ */

/**
 * Entrance the song warps to. 0x614 is the index produced by the
 * ENTR_VERSAS_FATE line you append to soh/include/tables/entrance_table.h
 * (the vanilla table ends at 0x613).  Keep the two in sync - if you add the
 * entry at the END of the table, as APPLY.md says, this value needs no change.
 */
#ifndef VF_ENTRANCE_INDEX
#define VF_ENTRANCE_INDEX 0x614
#endif

/**
 * Fanfare played while the screen fades. NA_BGM_OCA_MINUET is the vanilla
 * "you played the Minuet" jingle, i.e. exactly what the game plays when you
 * play a real song, but it is filed under the *Ocarina* category in SoH's
 * Audio Editor, and that category cannot be pointed at a custom track.
 *
 * To hear the mod's own melody instead, do this:
 *   1. change the line below to NA_BGM_APPEAR ("Enter Zelda" - a fanfare that
 *      only plays during one cutscene, so it is safe to hijack),
 *   2. rebuild,
 *   3. in game: Enhancements -> Audio Editor -> Fanfares -> "Enter Zelda"
 *      -> select "Versas Lullaby".
 * See docs/CUSTOM_MUSIC.md for the full explanation of that limitation.
 */
#ifndef VF_WARP_FANFARE
#define VF_WARP_FANFARE NA_BGM_OCA_MINUET
#endif

/**
 * Bending the stick further than this (as a fraction of the unbent pitch)
 * counts as "not the note that was played", mirroring the vanilla check that
 * throws away notes bent by more than 20 analog units.
 */
#define VF_MAX_BEND 0.05f

/* ------------------------------------------------------------------------ *
 * The song
 * ------------------------------------------------------------------------ */

/** D4, D5, F4, B4, A4, D4  ==  A, C-Up, C-Down, C-Left, C-Right, A */
static const u8 sVersasLullaby[] = {
    OCARINA_PITCH_D4, OCARINA_PITCH_D5, OCARINA_PITCH_F4, OCARINA_PITCH_B4, OCARINA_PITCH_A4, OCARINA_PITCH_D4,
};

static size_t sVersasLullabyPos = 0;
static u8 sVersasLullabyLastPitch = OCARINA_PITCH_NONE;

/* ------------------------------------------------------------------------ *
 * Warp
 * ------------------------------------------------------------------------ */

static void VersasFate_Warp(void) {
    // Close the "Play using [A] and [C]" textbox and put the ocarina away.
    // Same sequence PauseWarp uses for the vanilla warp songs.
    Message_CloseTextbox(gPlayState);
    AudioOcarina_SetInstrument(OCARINA_INSTRUMENT_OFF);
    Audio_PlayFanfare(VF_WARP_FANFARE);

    // Hand over to the transition system. OTRPlay_SpawnScene() resolves
    // VF_ENTRANCE_INDEX through gEntranceTable, finds SCENE_VERSAS_FATE and
    // loads scenes/shared/versa_scene/versa_scene out of VersasFate.o2r.
    gPlayState->nextEntranceIndex = VF_ENTRANCE_INDEX;
    gPlayState->transitionType = TRANS_TYPE_FADE_WHITE_FAST;
    gPlayState->transitionTrigger = TRANS_TRIGGER_START;
}

/* ------------------------------------------------------------------------ *
 * Song detection
 * ------------------------------------------------------------------------ */

static void VersasFate_ResetSong(void) {
    sVersasLullabyPos = 0;
    sVersasLullabyLastPitch = OCARINA_PITCH_NONE;
}

/**
 * Called from AudioOcarina_PlayControllerInput() every frame the ocarina is
 * being played. `pitch` is the current note (OCARINA_PITCH_* value or
 * OCARINA_PITCH_NONE when nothing is held), `bendFreq` is the pitch bend
 * multiplier (1.0 = no bend). The third argument, the instrument id, is not
 * used here.
 */
static void VersasFate_OnOcarinaNote(uint8_t pitch, float bendFreq, int8_t instrument) {
    (void)instrument;

    if (gPlayState == nullptr || !GameInteractor::IsSaveLoaded(true)) {
        VersasFate_ResetSong();
        return;
    }

    // Freestyle play only: never during a song demonstration, the scarecrow
    // recording, the memory game or an ocarina-spot check.
    if (gPlayState->msgCtx.ocarinaAction != OCARINA_ACTION_FREE_PLAY) {
        VersasFate_ResetSong();
        return;
    }

    // The hook fires every frame with whatever note is held; only a *new*
    // pitch is an event, exactly like the engine's own sPrevOcarinaPitch
    // comparison. Releases (OCARINA_PITCH_NONE) are not notes.
    if (pitch == sVersasLullabyLastPitch) {
        return;
    }
    sVersasLullabyLastPitch = pitch;
    if (pitch == OCARINA_PITCH_NONE) {
        return;
    }

    // A note that has been bent away from its true pitch does not count.
    bool bent = (bendFreq < 1.0f - VF_MAX_BEND) || (bendFreq > 1.0f + VF_MAX_BEND);

    if (!bent && pitch == sVersasLullaby[sVersasLullabyPos]) {
        sVersasLullabyPos++;
        if (sVersasLullabyPos >= ARRAY_COUNT(sVersasLullaby)) {
            VersasFate_ResetSong();
            VersasFate_Warp();
        }
    } else {
        // Wrong note: restart, but let this note be the first note again so
        // that a repeated first note is not "eaten".
        sVersasLullabyPos = (pitch == sVersasLullaby[0]) ? 1 : 0;
    }
}

static void RegisterVersasFate() {
    COND_HOOK(OnOcarinaNote, true, VersasFate_OnOcarinaNote);
}

static RegisterShipInitFunc initFunc(RegisterVersasFate);
