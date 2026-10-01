/**
 * Versa's Fate - the only C++ this mod needs.
 *
 * Everything the mod *contains* (the Vine Forest scene, its rooms, its
 * objects, its six textures, its three music tracks) is data, and it all
 * lives in VersasFate.o2r: drag the archive into the mods folder and the
 * engine loads it, no code involved. Three things cannot be done from an
 * archive, and they are the only three things in this file:
 *
 *   1. THE VINE PADS. OoT scene files decide what exists in a map, and a mod
 *      cannot append an entry to a *vanilla* scene's actor list without
 *      shipping a copy of that whole scene. So the pads themselves - a ring
 *      of vines drawn on the ground, and the "stand on it and travel" check -
 *      are done here, from the port's per-frame and per-draw hooks. They appear
 *      in Kokiri Forest, Hyrule Field and Kakariko Village, a couple of steps
 *      in front of Link wherever he walks into that area, and standing in the
 *      middle of one takes him to Versa's Vine Forest.
 *
 *   2. THE SONG. Playing A, C-Up, C-Down, C-Left, C-Right, A on the ocarina
 *      warps as well. The engine exposes an OnOcarinaNote hook that fires for
 *      every note, so the melody is matched here rather than by adding a song
 *      to the vanilla song list (which mods cannot touch, and which would have
 *      needed new ocarina-song data in the save file). Nothing vanilla
 *      changes, and no song has to be "learned": the run of notes is matched
 *      by ear. See docs/CUSTOM_MUSIC.md for why the *song* is code but the
 *      *music* is an archive resource.
 *
 *   3. THE KOKIRI LESSON. Saria (or any other Kokiri) sings the melody once
 *      per session when you talk to her with the ocarina in hand. Flavour
 *      only: nothing is unlocked, the warp works before and after it.
 *
 * Build: this file is picked up automatically by the glob in
 * soh/CMakeLists.txt, so it is enough to re-run CMake (or just build) after
 * copying it in. See patch/APPLY.md for the full Windows walkthrough, and
 * build_it.bat for the double-click version of it.
 */

#include "soh/ShipInit.hpp"
#include "soh/Enhancements/audio/AudioCollection.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Enhancements/game-interactor/GameInteractor_Hooks.h"
#include "soh/Notification/Notification.h"

#include <cmath>
#include <cstdint>
#include <vector>

extern "C" {
#include <z64.h>
#include "functions.h"
#include "macros.h"
#include "variables.h"
#include "z64save.h"
}

extern "C" PlayState* gPlayState;

/* ------------------------------------------------------------------------ *
 * Configuration
 * ------------------------------------------------------------------------ */

/**
 * Entrance the pads and the song warp to. 0x614 is the index produced by the
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
 * The vine pads
 * ------------------------------------------------------------------------ *
 *
 * Where they are: inside each of the three areas in sVersasFatePads, a ring of
 * vines is drawn on the ground about VF_PAD_FORWARD_DISTANCE units in front of
 * wherever Link appears when he walks into that area. Hooking onto the entry
 * point instead of a hardcoded coordinate means the pad is always on walkable
 * ground and always in sight - there is no way to guess an OoT world position
 * that is guaranteed to be open floor in somebody else's save.
 *
 * Standing in the middle of it (VF_PAD_TRIGGER_RADIUS) warps to the Vine
 * Forest, but only after Link has first stepped *off* the pad - otherwise
 * arriving in one of those areas, which happens with the pad underfoot when he
 * comes back from the forest, would immediately bounce him in again.
 */

static constexpr f32 VF_PAD_FORWARD_DISTANCE = 90.0f;
static constexpr f32 VF_PAD_INNER_RADIUS = 26.0f;
static constexpr f32 VF_PAD_OUTER_RADIUS = 45.0f;
static constexpr f32 VF_PAD_LEAF_RADIUS = 56.0f;
static constexpr f32 VF_PAD_TRIGGER_RADIUS = 40.0f;
static constexpr f32 VF_PAD_ARM_RADIUS = 70.0f;
static constexpr f32 VF_PAD_HINT_RADIUS = 220.0f;
static constexpr f32 VF_PAD_GROUND_OFFSET = 3.0f;
static constexpr u16 VF_PAD_ARM_FRAMES = 15;
static constexpr f32 VF_PAD_FOLLOW_RADIUS = 300.0f;
static constexpr f32 VF_DEG_TO_RAD = 3.14159265358979f / 180.0f;
static constexpr f32 VF_YAW_TO_RAD = 3.14159265358979f / 32768.0f;

/**
 * Two things gbi.h does not provide, taken from the port's own collision
 * viewer (soh/soh/Enhancements/debugger/colViewer.cpp): a flat "primitive
 * colour" combine mode, and a helper that builds a Vtx with explicit normals
 * and alpha. Both are used for the pad mosaic below.
 */
#define VF_CC_PRIMITIVE_ENVA 0, 0, 0, PRIMITIVE, 0, 0, 0, ENVIRONMENT
#define vfSPDefVtx(x, y, z, s, t, nx, ny, nz, ca)                                             \
    {                                                                                         \
        .n = { .ob = { x, y, z }, .tc = { (int16_t)((s) * 0x0020), (int16_t)((t) * 0x0020) }, \
               .n = { nx, ny, nz }, .a = ca }                                                 \
    }

struct VersasFatePad {
    s16 scene;
    const char* name;
};

static const VersasFatePad sVersasFatePads[] = {
    { SCENE_KOKIRI_FOREST, "Kokiri Forest" },
    { SCENE_HYRULE_FIELD, "Hyrule Field" },
    { SCENE_KAKARIKO_VILLAGE, "Kakariko Village" },
};

static s32 sPadIndex = -1;
static s16 sPadLastScene = -1;
static Vec3f sPadPos = { 0.0f, 0.0f, 0.0f };
static Vec3f sPadBuiltAt = { 0.0f, 0.0f, 0.0f };
static bool sPadPlaced = false;
static bool sPadArmed = false;
static bool sPadHintShown = false;
static bool sPadBuilt = false;
static u16 sPadFramesOutside = 0;
static std::vector<Vtx> sPadVtx;
static std::vector<Gfx> sPadGfx;

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
 * The Kokiri lesson
 * ------------------------------------------------------------------------ *
 *
 * A Kokiri in Kokiri Forest sings the melody for you the first time you talk
 * to one (with the ocarina in your inventory), once per play session. That is
 * the "an NPC teaches me the song" moment: the notes are not stored anywhere
 * and nothing is unlocked - the song works before and after the lesson. It is
 * flavour, not a gate.
 *
 * Saria (En_Sa) is the teacher. She is the one who hands you the ocarina, and
 * she does that in Sacred Forest Meadow, so the lesson is available there as
 * well as in Kokiri Forest. Every other Kokiri (En_Ko) teaches in Kokiri
 * Forest, so this still works in save states where Saria has moved on.
 *
 * The melody it sings is the mod's own "Versas Lullaby" sequence out of the
 * .o2r (looked up by name among the custom sequences the archive registered);
 * if the archive is not installed it falls back to the vanilla Minuet jingle
 * rather than staying silent.
 */

static bool sLessonPending = false;
static bool sLessonPlayed = false;

/** The sequence id the engine gave the mod's melody, or the Minuet jingle. */
static u16 VersasFate_LullabySequence(void) {
    for (const auto& [seqId, info] : AudioCollection::Instance->GetAllSequences()) {
        if (info.label == "Versas Lullaby") {
            return seqId;
        }
    }
    return NA_BGM_OCA_MINUET;
}

/** Notice the player starting to talk to their teacher. */
static void VersasFate_OnActorUpdate(void* actorPtr) {
    if (sLessonPlayed || sLessonPending || gPlayState == nullptr || !GameInteractor::IsSaveLoaded(true)) {
        return;
    }
    // Without the ocarina there is nothing to teach with.
    if (gSaveContext.inventory.items[SLOT_OCARINA] == ITEM_NONE) {
        return;
    }

    Actor* actor = static_cast<Actor*>(actorPtr);

    // Saria teaches wherever she can be talked to (Kokiri Forest early on,
    // Sacred Forest Meadow - where she hands over the ocarina - afterwards).
    // Every other Kokiri teaches in Kokiri Forest, for saves where she is not
    // around any more.
    const bool isSaria = (actor->id == ACTOR_EN_SA);
    const bool isOtherKokiri = (actor->id == ACTOR_EN_KO);

    const bool placeIsRight =
        isSaria ? (gPlayState->sceneNum == SCENE_KOKIRI_FOREST || gPlayState->sceneNum == SCENE_SACRED_FOREST_MEADOW)
                : (isOtherKokiri && gPlayState->sceneNum == SCENE_KOKIRI_FOREST);
    if (!placeIsRight) {
        return;
    }

    if (GET_PLAYER(gPlayState)->talkActor != actor) {
        return;
    }

    sLessonPending = true;
}

/* ------------------------------------------------------------------------ *
 * Warp
 * ------------------------------------------------------------------------ */

static void VersasFate_Warp(bool fromOcarina) {
    if (fromOcarina) {
        // Close the "Play using [A] and [C]" textbox and put the ocarina away.
        // Same sequence PauseWarp uses for the vanilla warp songs.
        Message_CloseTextbox(gPlayState);
        AudioOcarina_SetInstrument(OCARINA_INSTRUMENT_OFF);
    }

    Audio_PlayFanfare(VF_WARP_FANFARE);

    // Hand over to the transition system. OTRPlay_SpawnScene() resolves
    // VF_ENTRANCE_INDEX through gEntranceTable, finds SCENE_VERSAS_FATE and
    // loads scenes/shared/versa_scene/versa_scene out of VersasFate.o2r.
    gPlayState->nextEntranceIndex = VF_ENTRANCE_INDEX;
    gPlayState->transitionType = TRANS_TYPE_FADE_WHITE_FAST;
    gPlayState->transitionTrigger = TRANS_TRIGGER_START;
}

/* ------------------------------------------------------------------------ *
 * Pad bookkeeping - runs once per frame while a save is loaded
 * ------------------------------------------------------------------------ */

/** Forget everything about the previous area and look for a pad in this one. */
static void VersasFate_EnterScene(s16 sceneNum) {
    sPadLastScene = sceneNum;
    sPadIndex = -1;
    for (s32 i = 0; i < static_cast<s32>(ARRAY_COUNT(sVersasFatePads)); i++) {
        if (sVersasFatePads[i].scene == sceneNum) {
            sPadIndex = i;
            break;
        }
    }
    sPadPlaced = false;
    sPadArmed = false;
    sPadHintShown = false;
    sPadBuilt = false;
    sPadFramesOutside = 0;
}

static void VersasFate_PadUpdate(void) {
    if (gPlayState == nullptr || !GameInteractor::IsSaveLoaded(true)) {
        return;
    }

    if (gPlayState->sceneNum != sPadLastScene) {
        VersasFate_EnterScene(gPlayState->sceneNum);
    }
    if (sPadIndex < 0) {
        return;
    }

    Player* player = GET_PLAYER(gPlayState);
    if (player == nullptr || player->actor.update == nullptr) {
        return;
    }

    const Vec3f& pos = player->actor.world.pos;

    // Place the pad the first time we see Link standing still in this area,
    // i.e. once the fade from the previous map is over and the entrance has
    // put him where it wants him: two steps ahead of his own two feet.
    if (!sPadPlaced) {
        if (gPlayState->transitionTrigger != TRANS_TRIGGER_OFF) {
            return;
        }
        const f32 yaw = static_cast<f32>(player->actor.world.rot.y) * VF_YAW_TO_RAD;
        sPadPos.x = pos.x + sinf(yaw) * VF_PAD_FORWARD_DISTANCE;
        sPadPos.z = pos.z + cosf(yaw) * VF_PAD_FORWARD_DISTANCE;
        sPadPos.y = pos.y;
        sPadPlaced = true;
    }

    const f32 dx = pos.x - sPadPos.x;
    const f32 dz = pos.z - sPadPos.z;
    const f32 distSq = (dx * dx) + (dz * dz);

    // Stay glued to the local floor: while the pad is in sight it follows the
    // height of Link's feet, so slopes and steps cannot bury it.
    if (distSq < VF_PAD_FOLLOW_RADIUS * VF_PAD_FOLLOW_RADIUS) {
        sPadPos.y = pos.y;
    }

    // Armed = "was away from the pad long enough that stepping onto it is a
    // decision". Arriving in the area does not count.
    if (distSq > VF_PAD_ARM_RADIUS * VF_PAD_ARM_RADIUS) {
        if (sPadFramesOutside < 0xFFFF) {
            sPadFramesOutside++;
        }
    } else {
        sPadFramesOutside = 0;
    }
    if (sPadFramesOutside >= VF_PAD_ARM_FRAMES) {
        sPadArmed = true;
    }

    if (!sPadHintShown && distSq < VF_PAD_HINT_RADIUS * VF_PAD_HINT_RADIUS) {
        sPadHintShown = true;
        Notification::Emit({
            .prefix = "Versa's Fate",
            .prefixColor = ImVec4(0.45f, 0.85f, 0.45f, 1.0f),
            .message = std::string("A vine pad hums in the grass of ") + sVersasFatePads[sPadIndex].name +
                       " - step into the middle of it to travel to Versa's Vine Forest.",
            .messageColor = ImVec4(0.82f, 0.95f, 0.82f, 1.0f),
            .remainingTime = 6.0f,
        });
    }

    if (!sPadArmed || distSq > VF_PAD_TRIGGER_RADIUS * VF_PAD_TRIGGER_RADIUS) {
        return;
    }
    // Never interrupt a fade or a cutscene.
    if (gPlayState->transitionTrigger != TRANS_TRIGGER_OFF || gPlayState->csCtx.state != CS_STATE_IDLE) {
        return;
    }

    sPadArmed = false;
    sPadFramesOutside = 0;
    VersasFate_Warp(false);
}

/* ------------------------------------------------------------------------ *
 * Drawing the pad - runs once per frame, inside the map's draw
 * ------------------------------------------------------------------------ */

/**
 * The pad is a flat mosaic of triangles laid on the ground and built straight
 * into the display list with world-space coordinates: no object file, no
 * texture, no actor, nothing that can fail to load. The recipe (decal render
 * mode, primitive-colour combine, gMtxClear) is the one the port's own
 * collision viewer uses to draw on top of the scene, so it is known to work on
 * every platform SoH runs on.
 */
static void VersasFate_BuildPadVerts(void) {
    constexpr s32 kSegments = 12;
    const f32 y = sPadPos.y + VF_PAD_GROUND_OFFSET;

    sPadVtx.clear();
    sPadVtx.reserve(1 + (kSegments * 2) + (kSegments / 2));

    // Centre, then the two rings, then one leaf tip between every second pair.
    sPadVtx.push_back(vfSPDefVtx(static_cast<short>(lroundf(sPadPos.x)), static_cast<short>(lroundf(y)),
                                  static_cast<short>(lroundf(sPadPos.z)), 0, 0, 0, 127, 0, 0xFF));

    for (s32 i = 0; i < kSegments; i++) {
        const f32 angle = static_cast<f32>(i) * (360.0f / static_cast<f32>(kSegments)) * VF_DEG_TO_RAD;
        sPadVtx.push_back(vfSPDefVtx(static_cast<short>(lroundf(sPadPos.x + (cosf(angle) * VF_PAD_INNER_RADIUS))),
                                      static_cast<short>(lroundf(y)),
                                      static_cast<short>(lroundf(sPadPos.z + (sinf(angle) * VF_PAD_INNER_RADIUS))), 0, 0,
                                      0, 127, 0, 0xFF));
    }
    for (s32 i = 0; i < kSegments; i++) {
        const f32 angle = static_cast<f32>(i) * (360.0f / static_cast<f32>(kSegments)) * VF_DEG_TO_RAD;
        sPadVtx.push_back(vfSPDefVtx(static_cast<short>(lroundf(sPadPos.x + (cosf(angle) * VF_PAD_OUTER_RADIUS))),
                                      static_cast<short>(lroundf(y)),
                                      static_cast<short>(lroundf(sPadPos.z + (sinf(angle) * VF_PAD_OUTER_RADIUS))), 0, 0,
                                      0, 127, 0, 0xFF));
    }
    for (s32 i = 0; i < kSegments / 2; i++) {
        const f32 angle =
            (15.0f + (static_cast<f32>(i) * (720.0f / static_cast<f32>(kSegments)))) * VF_DEG_TO_RAD;
        sPadVtx.push_back(vfSPDefVtx(static_cast<short>(lroundf(sPadPos.x + (cosf(angle) * VF_PAD_LEAF_RADIUS))),
                                      static_cast<short>(lroundf(y)),
                                      static_cast<short>(lroundf(sPadPos.z + (sinf(angle) * VF_PAD_LEAF_RADIUS))), 0, 0,
                                      0, 127, 0, 0xFF));
    }

    sPadBuiltAt = sPadPos;
    sPadBuilt = true;
}

static void VersasFate_DrawPad(void) {
    if (gPlayState == nullptr || sPadIndex < 0 || !sPadPlaced) {
        return;
    }
    if (gPlayState->sceneNum != sVersasFatePads[sPadIndex].scene) {
        return;
    }

    constexpr s32 kSegments = 12;

    if (!sPadBuilt || sPadBuiltAt.x != sPadPos.x || sPadBuiltAt.y != sPadPos.y || sPadBuiltAt.z != sPadPos.z) {
        VersasFate_BuildPadVerts();
    }
    if (sPadVtx.size() != static_cast<size_t>(1 + (kSegments * 2) + (kSegments / 2))) {
        return;
    }

    const u32 renderMode = Z_CMP | Z_UPD | CVG_DST_CLAMP | FORCE_BL | ZMODE_DEC;

    sPadGfx.clear();
    sPadGfx.push_back(gsSPTexture(0, 0, 0, G_TX_RENDERTILE, G_OFF));
    sPadGfx.push_back(gsDPSetCycleType(G_CYC_1CYCLE));
    sPadGfx.push_back(gsDPSetRenderMode(renderMode | GBL_c1(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1),
                                        renderMode | GBL_c2(G_BL_CLR_IN, G_BL_0, G_BL_CLR_IN, G_BL_1)));
    sPadGfx.push_back(gsDPSetCombineMode(VF_CC_PRIMITIVE_ENVA, VF_CC_PRIMITIVE_ENVA));
    sPadGfx.push_back(gsSPLoadGeometryMode(G_ZBUFFER));
    sPadGfx.push_back(gsDPSetEnvColor(0xFF, 0xFF, 0xFF, 0xFF));
    sPadGfx.push_back(gsSPMatrix(&gMtxClear, G_MTX_MODELVIEW | G_MTX_LOAD | G_MTX_NOPUSH));
    sPadGfx.push_back(gsSPVertex(reinterpret_cast<uintptr_t>(sPadVtx.data()), static_cast<u32>(sPadVtx.size()), 0));

    // Centre: the moss the vines grow out of.
    sPadGfx.push_back(gsDPSetPrimColor(0, 0, 28, 62, 30, 255));
    for (s32 i = 0; i < kSegments; i++) {
        sPadGfx.push_back(gsSP1Triangle(0, 1 + i, 1 + ((i + 1) % kSegments), 0));
    }

    // Ring: the woven vines themselves.
    sPadGfx.push_back(gsDPSetPrimColor(0, 0, 62, 128, 58, 255));
    for (s32 i = 0; i < kSegments; i++) {
        const s32 inner = 1 + i;
        const s32 innerNext = 1 + ((i + 1) % kSegments);
        const s32 outer = 1 + kSegments + i;
        const s32 outerNext = 1 + kSegments + ((i + 1) % kSegments);
        sPadGfx.push_back(gsSP2Triangles(inner, outer, outerNext, 0, inner, outerNext, innerNext, 0));
    }

    // Leaf tips poking out of the ring.
    sPadGfx.push_back(gsDPSetPrimColor(0, 0, 128, 210, 96, 255));
    for (s32 i = 0; i < kSegments / 2; i++) {
        sPadGfx.push_back(gsSP1Triangle(1 + (kSegments * 2) + i, 1 + kSegments + (i * 2),
                                        1 + kSegments + (((i * 2) + 1) % kSegments), 0));
    }

    sPadGfx.push_back(gsSPEndDisplayList());

    OPEN_DISPS(gPlayState->state.gfxCtx);
    gSPDisplayList(POLY_OPA_DISP++, sPadGfx.data());
    CLOSE_DISPS(gPlayState->state.gfxCtx);
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
            VersasFate_Warp(true);
        }
    } else {
        // Wrong note: restart, but let this note be the first note again so
        // that a repeated first note is not "eaten".
        sVersasLullabyPos = (pitch == sVersasLullaby[0]) ? 1 : 0;
    }
}

/* ------------------------------------------------------------------------ *
 * Per-frame housekeeping
 * ------------------------------------------------------------------------ */

/** When a conversation with a Kokiri ends, they sing the melody. */
static void VersasFate_OnGameFrameUpdate(void) {
    if (gPlayState == nullptr) {
        return;
    }

    if (sLessonPending) {
        // Wait for the textbox to close so the singing is not buried under it.
        if (gPlayState->msgCtx.msgMode == MSGMODE_NONE) {
            sLessonPending = false;
            sLessonPlayed = true;
            Audio_PlayFanfare(VersasFate_LullabySequence());
        }
    }

    VersasFate_PadUpdate();
}

static void RegisterVersasFate() {
    COND_HOOK(OnOcarinaNote, true, VersasFate_OnOcarinaNote);

    // The lesson: Saria in Kokiri Forest sings the melody - and any other
    // Kokiri does too, for saves where Saria has moved on.
    COND_ID_HOOK(OnActorUpdate, ACTOR_EN_SA, true, VersasFate_OnActorUpdate);
    COND_ID_HOOK(OnActorUpdate, ACTOR_EN_KO, true, VersasFate_OnActorUpdate);

    COND_HOOK(OnGameFrameUpdate, true, VersasFate_OnGameFrameUpdate);
    COND_HOOK(OnPlayDrawEnd, true, VersasFate_DrawPad);
}

static RegisterShipInitFunc initFunc(RegisterVersasFate);
