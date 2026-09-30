/**
 * Saria's Silver Rupee Trial
 *
 * A Kokiri Forest minigame: talking to Saria challenges Link to collect a number of silver rupees
 * scattered around the forest. Until the challenge is completed, a magic seal blocks the chamber
 * that holds the Kokiri Sword, so the trial has to be beaten before Mido can be shown a sword.
 *
 * How it works
 * - The seal is a custom actor (registered through ActorDB) made of solid, non pushable collision
 *   plus a translucent display list. It is spawned on top of the Kokiri Sword chest (identified by
 *   its treasure flag, which is unique in Kokiri Forest) as long as the chest is still closed and
 *   the trial has not been completed on the save file.
 * - Completing the trial sets a permanent flag (INFTABLE_SARIA_RUPEE_GAME), which removes the seal
 *   for good and stops the mod from touching Saria's dialogue.
 * - The silver rupees are real ACTOR_EN_G_SWITCH silver rupees, so they look, sound and pay out
 *   (5 rupees) exactly like the ones in Shadow Temple or the Gerudo Training Ground. They are
 *   spawned procedurally around Saria, snapped to the floor with a collision raycast, and are
 *   despawned if the trial is abandoned.
 *
 * The mod disables itself while a randomizer seed is running, because the randomizer owns the
 * silver rupee hooks (VB_SILVER_COLLECT / VB_SILVER_DESPAWN) and the Kokiri Sword chest location.
 */

#include <libultraship/bridge/consolevariablebridge.h>

#include "soh/ActorDB.h"
#include "soh/Enhancements/custom-message/CustomMessageManager.h"
#include "soh/Enhancements/custom-message/CustomMessageTypes.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Notification/Notification.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

extern "C" {
#include "functions.h"
#include "macros.h"
#include "variables.h"
#include "src/overlays/actors/ovl_En_Box/z_en_box.h"
#include "src/overlays/actors/ovl_En_G_Switch/z_en_g_switch.h"

extern PlayState* gPlayState;
extern SaveContext gSaveContext;
}

#define SARIA_GAME_DEFAULT_RUPEE_COUNT 10
#define SARIA_GAME_DEFAULT_SEARCH_RADIUS 600
#define SARIA_GAME_DEFAULT_SEAL_SIZE 150
#define SARIA_GAME_MAX_RUPEES 30

#define CVAR_ENABLED_NAME CVAR_ENHANCEMENT("SariaRupeeGame.Enabled")
#define CVAR_ENABLED CVarGetInteger(CVAR_ENABLED_NAME, 0)
#define CVAR_RUPEE_COUNT_NAME CVAR_ENHANCEMENT("SariaRupeeGame.RupeeCount")
#define CVAR_RUPEE_COUNT CVarGetInteger(CVAR_RUPEE_COUNT_NAME, SARIA_GAME_DEFAULT_RUPEE_COUNT)
#define CVAR_SEARCH_RADIUS_NAME CVAR_ENHANCEMENT("SariaRupeeGame.SearchRadius")
#define CVAR_SEARCH_RADIUS CVarGetInteger(CVAR_SEARCH_RADIUS_NAME, SARIA_GAME_DEFAULT_SEARCH_RADIUS)
#define CVAR_SEAL_SIZE_NAME CVAR_ENHANCEMENT("SariaRupeeGame.SealSize")
#define CVAR_SEAL_SIZE CVarGetInteger(CVAR_SEAL_SIZE_NAME, SARIA_GAME_DEFAULT_SEAL_SIZE)

// The Kokiri Sword chest is the only chest in Kokiri Forest, and it uses treasure flag 0.
#define SARIA_GAME_CHEST_FLAG 0x00
// Switch flag used by our silver rupees. Kokiri Forest has no vanilla silver rupees, so this value
// is only ever seen by the rupees spawned by this mod.
#define SARIA_GAME_SILVER_FLAG 0x30
#define SARIA_GAME_SILVER_PARAMS ((ENGSWITCH_SILVER_RUPEE << 0xC) | SARIA_GAME_SILVER_FLAG)

// Text ids used by this mod. They are outside of every table shipped with the game and are only
// ever opened through our OnOpenText hooks, which always feed them a custom message.
#define TEXT_SARIA_TRIAL_SEAL 0x8F10
#define TEXT_SARIA_TRIAL_COMPLETE 0x8F12

struct SariaRupeeGameState {
    bool trialActive = false;
    bool pendingStart = false;
    bool pendingCompleteText = false;
    int32_t collected = 0;
    int32_t target = 0;
};

static SariaRupeeGameState sState;
static int32_t sSealActorId = -1;

// region Seal barrier actor

typedef struct SariaSeal {
    /* 0x000 */ DynaPolyActor dyna;
    /* 0x164 */ s16 timer;
    /* 0x166 */ s16 talking;
} SariaSeal;

// Local collision bounds. The actor's scale turns these into world units, so a scale of
// size / SARIA_SEAL_LOCAL_HEIGHT makes a cube of `size` units.
#define SARIA_SEAL_LOCAL_HALF 500
#define SARIA_SEAL_LOCAL_HEIGHT 1000

// Surface type 0: no wall flags, so the seal cannot be climbed, laddered, crawled through or
// pushed around by the player.
static SurfaceType sSealSurfaceType = { { 0, 0 } };
static CamData sSealCamData = { 0, 0, NULL };

static Vec3s sSealColVtxList[] = {
    /* 0 */ { -SARIA_SEAL_LOCAL_HALF, 0, -SARIA_SEAL_LOCAL_HALF },
    /* 1 */ { SARIA_SEAL_LOCAL_HALF, 0, -SARIA_SEAL_LOCAL_HALF },
    /* 2 */ { SARIA_SEAL_LOCAL_HALF, 0, SARIA_SEAL_LOCAL_HALF },
    /* 3 */ { -SARIA_SEAL_LOCAL_HALF, 0, SARIA_SEAL_LOCAL_HALF },
    /* 4 */ { -SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, -SARIA_SEAL_LOCAL_HALF },
    /* 5 */ { SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, -SARIA_SEAL_LOCAL_HALF },
    /* 6 */ { SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, SARIA_SEAL_LOCAL_HALF },
    /* 7 */ { -SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, SARIA_SEAL_LOCAL_HALF },
};

// Every triangle is wound so that (vB - vA) x (vC - vA) points out of the box, which is the
// convention the collision code uses to rebuild normals in DynaPoly_ExpandSRT. `dist` is
// -normal . vtxA. The values below are only the initial ones; dynamic polys recompute both.
static CollisionPoly sSealPolyList[] = {
    // bottom (-y)
    { 0, { 0, 1, 2 }, { 0, -COLPOLY_SNORMAL(1.0f), 0 }, 0 },
    { 0, { 0, 2, 3 }, { 0, -COLPOLY_SNORMAL(1.0f), 0 }, 0 },
    // top (+y)
    { 0, { 4, 6, 5 }, { 0, COLPOLY_SNORMAL(1.0f), 0 }, -SARIA_SEAL_LOCAL_HEIGHT },
    { 0, { 4, 7, 6 }, { 0, COLPOLY_SNORMAL(1.0f), 0 }, -SARIA_SEAL_LOCAL_HEIGHT },
    // -z
    { 0, { 0, 5, 1 }, { 0, 0, -COLPOLY_SNORMAL(1.0f) }, -SARIA_SEAL_LOCAL_HALF },
    { 0, { 0, 4, 5 }, { 0, 0, -COLPOLY_SNORMAL(1.0f) }, -SARIA_SEAL_LOCAL_HALF },
    // +z
    { 0, { 2, 7, 3 }, { 0, 0, COLPOLY_SNORMAL(1.0f) }, -SARIA_SEAL_LOCAL_HALF },
    { 0, { 2, 6, 7 }, { 0, 0, COLPOLY_SNORMAL(1.0f) }, -SARIA_SEAL_LOCAL_HALF },
    // -x
    { 0, { 3, 4, 0 }, { -COLPOLY_SNORMAL(1.0f), 0, 0 }, -SARIA_SEAL_LOCAL_HALF },
    { 0, { 3, 7, 4 }, { -COLPOLY_SNORMAL(1.0f), 0, 0 }, -SARIA_SEAL_LOCAL_HALF },
    // +x
    { 0, { 1, 6, 2 }, { COLPOLY_SNORMAL(1.0f), 0, 0 }, -SARIA_SEAL_LOCAL_HALF },
    { 0, { 1, 5, 6 }, { COLPOLY_SNORMAL(1.0f), 0, 0 }, -SARIA_SEAL_LOCAL_HALF },
};

static CollisionHeader sSealColHeader = {
    { -SARIA_SEAL_LOCAL_HALF, 0, -SARIA_SEAL_LOCAL_HALF },                     // minBounds
    { SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, SARIA_SEAL_LOCAL_HALF }, // maxBounds
    ARRAY_COUNT(sSealColVtxList),
    sSealColVtxList,
    ARRAY_COUNT(sSealPolyList),
    sSealPolyList,
    &sSealSurfaceType,
    &sSealCamData,
    0,
    NULL,
    1, // cameraDataListLen
};

static Vtx sSealVtx[] = {
    VTX(-SARIA_SEAL_LOCAL_HALF, 0, -SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(SARIA_SEAL_LOCAL_HALF, 0, -SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(SARIA_SEAL_LOCAL_HALF, 0, SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(-SARIA_SEAL_LOCAL_HALF, 0, SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(-SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, -SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, -SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
    VTX(-SARIA_SEAL_LOCAL_HALF, SARIA_SEAL_LOCAL_HEIGHT, SARIA_SEAL_LOCAL_HALF, 0, 0, 255, 255, 255, 255),
};

static Gfx sSealDL[] = {
    gsDPPipeSync(),
    gsDPSetCombineMode(G_CC_PRIMITIVE, G_CC_PRIMITIVE),
    gsDPSetPrimColor(0, 0, 120, 210, 255, 150),
    gsDPSetRenderMode(G_RM_XLU_SURF, G_RM_XLU_SURF2),
    gsSPClearGeometryMode(G_CULL_BACK | G_FOG | G_LIGHTING | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR),
    gsSPVertex(sSealVtx, ARRAY_COUNT(sSealVtx), 0),
    gsSP2Triangles(0, 1, 2, 0, 0, 2, 3, 0),
    gsSP2Triangles(4, 6, 5, 0, 4, 7, 6, 0),
    gsSP2Triangles(0, 5, 1, 0, 0, 4, 5, 0),
    gsSP2Triangles(2, 7, 3, 0, 2, 6, 7, 0),
    gsSP2Triangles(3, 4, 0, 0, 3, 7, 4, 0),
    gsSP2Triangles(1, 6, 2, 0, 1, 5, 6, 0),
    gsDPPipeSync(),
    gsSPEndDisplayList(),
};

static void SariaSeal_Init(Actor* thisx, PlayState* play) {
    SariaSeal* self = (SariaSeal*)thisx;
    CollisionHeader* colHeader = NULL;
    f32 size = CLAMP((f32)CVAR_SEAL_SIZE, 40.0f, 600.0f);

    Actor_SetScale(thisx, size / SARIA_SEAL_LOCAL_HEIGHT);
    DynaPolyActor_Init(&self->dyna, DPM_UNK);
    CollisionHeader_GetVirtual(&sSealColHeader, &colHeader);
    self->dyna.bgId = DynaPoly_SetBgActor(play, &play->colCtx.dyna, thisx, colHeader);
    ActorShape_Init(&thisx->shape, 0.0f, NULL, 0.0f);
    // targetMode 6 is the NPC "talk" range, so Link gets a talk prompt instead of a look prompt.
    thisx->targetMode = 6;
    thisx->textId = TEXT_SARIA_TRIAL_SEAL;
    thisx->flags |= ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY;
    thisx->uncullZoneScale = 1000.0f;
    thisx->uncullZoneDownward = 1000.0f;
    self->timer = 0;
    self->talking = false;
}

static void SariaSeal_Destroy(Actor* thisx, PlayState* play) {
    SariaSeal* self = (SariaSeal*)thisx;

    DynaPoly_DeleteBgActor(play, &play->colCtx.dyna, self->dyna.bgId);
}

static void SariaSeal_Update(Actor* thisx, PlayState* play) {
    SariaSeal* self = (SariaSeal*)thisx;

    self->timer++;

    if (self->talking) {
        if (Actor_TextboxIsClosing(thisx, play)) {
            self->talking = false;
        }
        return;
    }

    if (Actor_ProcessTalkRequest(thisx, play)) {
        // Talking to the seal explains the trial and, if it has not started yet, starts it as soon
        // as the text box is closed.
        Message_StartTextbox(play, TEXT_SARIA_TRIAL_SEAL, thisx);
        if (!sState.trialActive) {
            sState.pendingStart = true;
        }
        self->talking = true;
    } else {
        Actor_OfferTalk(thisx, play, 100.0f);
    }
}

static void SariaSeal_Draw(Actor* thisx, PlayState* play) {
    SariaSeal* self = (SariaSeal*)thisx;
    // A slow, small pulse. Only the drawn model scales; the collision stays put.
    f32 pulse = 1.0f + 0.02f * Math_SinS(self->timer * 0x300);

    Matrix_Push();
    Matrix_Scale(pulse, pulse, pulse, MTXMODE_APPLY);
    Gfx_DrawDListXlu(play, sSealDL);
    Matrix_Pop();
}

static void SariaSeal_RegisterActor() {
    if (sSealActorId >= 0 || ActorDB::Instance == nullptr) {
        return;
    }

    ActorDBInit entry = {
        "En_SariaSeal",
        "Saria's Silver Rupee Seal",
        -1, // dynamic id
        ACTORCAT_NPC,
        (ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY | ACTOR_FLAG_UPDATE_CULLING_DISABLED |
         ACTOR_FLAG_DRAW_CULLING_DISABLED),
        OBJECT_GAMEPLAY_KEEP,
        sizeof(SariaSeal),
        (ActorFunc)SariaSeal_Init,
        (ActorFunc)SariaSeal_Destroy,
        (ActorFunc)SariaSeal_Update,
        (ActorFunc)SariaSeal_Draw,
        nullptr,
    };

    sSealActorId = ActorDB::Instance->AddEntry(entry).entry.id;
}

// endregion

// region helpers

static bool SariaRupeeGame_IsEnabled() {
    return CVAR_ENABLED && !IS_RANDO;
}

static bool SariaRupeeGame_IsComplete() {
    return Flags_GetInfTable(INFTABLE_SARIA_RUPEE_GAME);
}

// The seal exists while the mod is on, the Kokiri Sword has not been collected yet and the trial
// has not been beaten on this save file.
static bool SariaRupeeGame_ShouldSealExist() {
    return SariaRupeeGame_IsEnabled() && !LINK_IS_ADULT && !SariaRupeeGame_IsComplete() &&
           !Flags_GetTreasure(gPlayState, SARIA_GAME_CHEST_FLAG);
}

static Actor* SariaRupeeGame_FindKokiriSwordChest(PlayState* play) {
    Actor* actor = play->actorCtx.actorLists[ACTORCAT_CHEST].head;

    while (actor != NULL) {
        if (actor->id == ACTOR_EN_BOX && (actor->params & 0x1F) == SARIA_GAME_CHEST_FLAG) {
            return actor;
        }
        actor = actor->next;
    }

    return NULL;
}

static Actor* SariaRupeeGame_FindSeal(PlayState* play) {
    if (sSealActorId < 0) {
        return NULL;
    }

    return Actor_Find(&play->actorCtx, sSealActorId, ACTORCAT_NPC);
}

static void SariaRupeeGame_SpawnSeal(PlayState* play) {
    Actor* chest = SariaRupeeGame_FindKokiriSwordChest(play);
    Player* player = GET_PLAYER(play);
    f32 size = CLAMP((f32)CVAR_SEAL_SIZE, 40.0f, 600.0f);

    if (chest == NULL || player == NULL) {
        return;
    }

    // Never drop the seal on top of Link: wait for him to step away from the chest instead.
    if (Math_Vec3f_DistXYZ(&chest->world.pos, &player->actor.world.pos) < size) {
        return;
    }

    SariaSeal_RegisterActor();
    if (sSealActorId < 0) {
        return;
    }

    if (Actor_Spawn(&play->actorCtx, play, sSealActorId, chest->world.pos.x, chest->world.pos.y, chest->world.pos.z, 0,
                    0, 0, 0) != NULL) {
        Sfx_PlaySfxCentered(NA_SE_SY_TRE_BOX_APPEAR);
    }
}

static void SariaRupeeGame_DespawnRupees(PlayState* play) {
    Actor* actor = play->actorCtx.actorLists[ACTORCAT_PROP].head;

    while (actor != NULL) {
        if (actor->id == ACTOR_EN_G_SWITCH && actor->params == SARIA_GAME_SILVER_PARAMS) {
            Actor_Kill(actor);
        }
        actor = actor->next;
    }
}

// Spawns `count` silver rupees on walkable ground around Saria (or around Link when she is not
// loaded). Positions are picked randomly and validated with a floor raycast, so the mod does not
// need to know anything about Kokiri Forest's geometry.
static void SariaRupeeGame_SpawnRupees(PlayState* play) {
    static const s16 sMinDistanceSq = 80 * 80;
    Vec3f spawnedPositions[SARIA_GAME_MAX_RUPEES];
    Actor* saria = Actor_Find(&play->actorCtx, ACTOR_EN_SA, ACTORCAT_NPC);
    Player* player = GET_PLAYER(play);
    Vec3f anchor;
    f32 searchRadius = CLAMP((f32)CVAR_SEARCH_RADIUS, 100.0f, 2000.0f);
    int32_t count = CLAMP(sState.target, 1, SARIA_GAME_MAX_RUPEES);
    int32_t spawned = 0;

    if (player == NULL) {
        return;
    }

    anchor = (saria != NULL) ? saria->world.pos : player->actor.world.pos;

    for (int32_t attempt = 0; attempt < count * 40 && spawned < count; attempt++) {
        s16 angle = (s16)(Rand_ZeroOne() * 65536.0f);
        f32 distance = searchRadius * (0.35f + 0.65f * Rand_ZeroOne());
        CollisionPoly* floorPoly = NULL;
        Vec3f probe;
        Vec3f rupeePos;
        f32 floorY;
        bool tooClose = false;

        probe.x = anchor.x + distance * Math_SinS(angle);
        probe.y = anchor.y + 400.0f;
        probe.z = anchor.z + distance * Math_CosS(angle);

        floorY = BgCheck_EntityRaycastFloor1(&play->colCtx, &floorPoly, &probe);
        if (floorPoly == NULL || floorY <= BGCHECK_Y_MIN) {
            continue; // no ground there, off the edge of the map
        }
        // Reject roofs, cliffs and anything too far from the plaza Saria stands on.
        if (fabsf(floorY - anchor.y) > 300.0f) {
            continue;
        }

        rupeePos.x = probe.x;
        rupeePos.y = floorY + 25.0f;
        rupeePos.z = probe.z;

        for (int32_t i = 0; i < spawned; i++) {
            if (Math_Vec3f_DistXZ(&rupeePos, &spawnedPositions[i]) *
                    Math_Vec3f_DistXZ(&rupeePos, &spawnedPositions[i]) <
                sMinDistanceSq) {
                tooClose = true;
                break;
            }
        }
        if (tooClose) {
            continue;
        }

        if (Actor_Spawn(&play->actorCtx, play, ACTOR_EN_G_SWITCH, rupeePos.x, rupeePos.y, rupeePos.z, 0, 0, 0,
                        SARIA_GAME_SILVER_PARAMS) == NULL) {
            return;
        }

        spawnedPositions[spawned++] = rupeePos;
    }

    // Guarantee that the trial is winnable: anything that could not be placed on validated ground
    // is dropped right next to Saria, where the floor is known to be reachable.
    for (int32_t i = spawned; i < count; i++) {
        s16 angle = (s16)((i * 65536.0f) / count);
        CollisionPoly* floorPoly = NULL;
        Vec3f probe;
        f32 floorY;

        probe.x = anchor.x + 80.0f * Math_SinS(angle);
        probe.y = anchor.y + 400.0f;
        probe.z = anchor.z + 80.0f * Math_CosS(angle);

        floorY = BgCheck_EntityRaycastFloor1(&play->colCtx, &floorPoly, &probe);
        if (floorPoly == NULL || floorY <= BGCHECK_Y_MIN) {
            floorY = anchor.y;
        }

        if (Actor_Spawn(&play->actorCtx, play, ACTOR_EN_G_SWITCH, probe.x, floorY + 25.0f, probe.z, 0, 0, 0,
                        SARIA_GAME_SILVER_PARAMS) == NULL) {
            return;
        }
    }
}

static void SariaRupeeGame_NotifyProgress() {
    Notification::Emit({
        .prefix = "Silver Rupees",
        .message = std::to_string(sState.collected) + " / " + std::to_string(sState.target),
        .remainingTime = 3.0f,
        .mute = true,
    });
}

static void SariaRupeeGame_StartTrial(PlayState* play) {
    sState.pendingStart = false;
    sState.collected = 0;
    sState.target = CLAMP(CVAR_RUPEE_COUNT, 1, SARIA_GAME_MAX_RUPEES);
    sState.trialActive = true;

    SariaRupeeGame_SpawnRupees(play);
    Sfx_PlaySfxCentered(NA_SE_SY_DECIDE);
    SariaRupeeGame_NotifyProgress();
}

static void SariaRupeeGame_CompleteTrial(PlayState* play) {
    Actor* seal = SariaRupeeGame_FindSeal(play);

    Flags_SetInfTable(INFTABLE_SARIA_RUPEE_GAME);
    sState.trialActive = false;
    sState.pendingStart = false;
    sState.pendingCompleteText = true;

    SariaRupeeGame_DespawnRupees(play);
    if (seal != NULL) {
        Actor_Kill(seal);
    }

    Sfx_PlaySfxCentered(NA_SE_SY_CORRECT_CHIME);
    Notification::Emit({
        .prefix = "Saria's seal",
        .message = "has been lifted!",
        .mute = true,
    });
}

static void SariaRupeeGame_OnRupeeCollected(PlayState* play) {
    static const s8 sMajorScale[] = { 0, 2, 4, 5, 7, 9, 11, 13, 15, 17 };

    sState.collected++;

    // The ascending jingle the vanilla silver rupee "tracker" actor plays.
    if (sState.collected <= (s32)ARRAY_COUNT(sMajorScale)) {
        Audio_PlaySoundTransposed(&gSfxDefaultPos, NA_SE_EV_FIVE_COUNT_LUPY, sMajorScale[sState.collected - 1]);
    }
    SariaRupeeGame_NotifyProgress();

    if (sState.collected >= sState.target) {
        SariaRupeeGame_CompleteTrial(play);
    }
}

// Drops the trial state without touching actors. Used when leaving Kokiri Forest, where the
// rupees are gone anyway.
static void SariaRupeeGame_AbandonTrial() {
    sState.trialActive = false;
    sState.pendingStart = false;
    sState.collected = 0;
}

// endregion

// region text

static void SariaRupeeGame_BuildOfferText(CustomMessage& msg) {
    // '@' is replaced with the file's player name by CustomMessage::AutoFormat.
    msg = CustomMessage("%gSaria%w: \"The %rKokiri Sword%w is locked&away behind my magic, @!&"
                        "Find me %r[[count]] silver rupees%w hidden&around the forest and the seal will&lift!\"");
    msg.Replace("[[count]]", std::to_string(CLAMP(CVAR_RUPEE_COUNT, 1, SARIA_GAME_MAX_RUPEES)));
}

static void SariaRupeeGame_BuildProgressText(CustomMessage& msg) {
    msg = CustomMessage("Silver rupees found: %r[[collected]]%w / %r[[count]]%w.&"
                        "The seal on the %gKokiri Sword%w&is still holding...");
    msg.Replace("[[collected]]", std::to_string(sState.collected));
    msg.Replace("[[count]]", std::to_string(sState.target));
}

// Text shown when talking to the seal in front of the Kokiri Sword chest.
static void SariaRupeeGame_SealText(uint16_t* textId, bool* loadFromMessageTable) {
    CustomMessage msg;

    if (sState.trialActive) {
        SariaRupeeGame_BuildProgressText(msg);
    } else {
        SariaRupeeGame_BuildOfferText(msg);
    }

    msg.AutoFormat();
    msg.LoadIntoFont();
    *loadFromMessageTable = false;
}

// Replaces Saria's Kokiri Forest lines with the trial offer (or the progress report) while the
// Kokiri Sword is still sealed away.
static void SariaRupeeGame_SariaText(uint16_t* textId, bool* loadFromMessageTable) {
    CustomMessage msg;

    if (!SariaRupeeGame_IsEnabled()) {
        return;
    }
    if (gPlayState == NULL || gPlayState->sceneNum != SCENE_KOKIRI_FOREST || LINK_IS_ADULT) {
        return;
    }
    if (SariaRupeeGame_IsComplete() || Flags_GetTreasure(gPlayState, SARIA_GAME_CHEST_FLAG)) {
        return;
    }

    if (sState.trialActive) {
        SariaRupeeGame_BuildProgressText(msg);
    } else {
        SariaRupeeGame_BuildOfferText(msg);
        // Start the trial once this text box is closed.
        sState.pendingStart = true;
    }

    msg.AutoFormat();
    msg.LoadIntoFont();
    *loadFromMessageTable = false;
}

static void SariaRupeeGame_CompleteText(uint16_t* textId, bool* loadFromMessageTable) {
    CustomMessage msg =
        CustomMessage("%gSaria%w: \"You did it, @!&The seal on the %rKokiri Sword%w is&lifted. Go get it!\"");

    msg.AutoFormat();
    msg.LoadIntoFont();
    *loadFromMessageTable = false;
}

// endregion

// region frame update

static void SariaRupeeGame_OnFrameUpdate() {
    PlayState* play = gPlayState;

    if (play == NULL || !play->state.running) {
        return;
    }

    bool inKokiriForest = play->sceneNum == SCENE_KOKIRI_FOREST;

    // Always registered, so turning the mod off (or loading a randomizer seed) still cleans up
    // anything this mod put into the scene.
    if (!SariaRupeeGame_IsEnabled()) {
        if (sState.trialActive || sState.pendingStart) {
            SariaRupeeGame_AbandonTrial();
            if (inKokiriForest) {
                SariaRupeeGame_DespawnRupees(play);
            }
        }
        if (inKokiriForest) {
            Actor* seal = SariaRupeeGame_FindSeal(play);
            if (seal != NULL) {
                Actor_Kill(seal);
            }
        }
        sState.pendingCompleteText = false;
        return;
    }

    if (!inKokiriForest) {
        // Leaving the forest abandons the trial: the rupees are unloaded with the scene.
        SariaRupeeGame_AbandonTrial();
        sState.pendingCompleteText = false;
        return;
    }

    if (sState.pendingCompleteText && play->msgCtx.msgMode == MSGMODE_NONE) {
        sState.pendingCompleteText = false;
        Message_StartTextbox(play, TEXT_SARIA_TRIAL_COMPLETE, SariaRupeeGame_FindSeal(play));
    }

    if (sState.pendingStart && play->msgCtx.msgMode == MSGMODE_NONE) {
        SariaRupeeGame_StartTrial(play);
    }

    if (SariaRupeeGame_ShouldSealExist()) {
        if (SariaRupeeGame_FindSeal(play) == NULL) {
            SariaRupeeGame_SpawnSeal(play);
        }
    } else {
        Actor* seal = SariaRupeeGame_FindSeal(play);
        if (seal != NULL) {
            Actor_Kill(seal);
        }
    }
}

// endregion

// region registration

static void SariaRupeeGame_RegisterTextHooks() {
    // NOTE: every COND_ID_HOOK expands to its own static hook id, so these have to be separate
    // statements. Looping over the ids would make each pass unregister the previous hook.
    COND_ID_HOOK(OnOpenText, TEXT_SARIA_TRIAL_SEAL, true, SariaRupeeGame_SealText);
    COND_ID_HOOK(OnOpenText, TEXT_SARIA_TRIAL_COMPLETE, true, SariaRupeeGame_CompleteText);

    // Saria's Kokiri Forest lines. The callback itself decides whether it takes over the text.
    COND_ID_HOOK(OnOpenText, 0x1001, true, SariaRupeeGame_SariaText);
    COND_ID_HOOK(OnOpenText, 0x1002, true, SariaRupeeGame_SariaText);
    COND_ID_HOOK(OnOpenText, 0x1003, true, SariaRupeeGame_SariaText);
    COND_ID_HOOK(OnOpenText, 0x1031, true, SariaRupeeGame_SariaText);
    COND_ID_HOOK(OnOpenText, 0x1032, true, SariaRupeeGame_SariaText);
}

static void SariaRupeeGame_RegisterGameplayHooks() {
    // Our silver rupees must never be despawned by the vanilla "switch flag already set" check.
    COND_VB_SHOULD(VB_SILVER_DESPAWN, CVAR_ENABLED && !IS_RANDO, {
        EnGSwitch* silver = va_arg(args, EnGSwitch*);

        if (gPlayState != NULL && gPlayState->sceneNum == SCENE_KOKIRI_FOREST &&
            silver->switchFlag == SARIA_GAME_SILVER_FLAG) {
            *should = false;
        }
    });

    // Count collected rupees. The vanilla collection (5 rupees, sound, actor removal) is left alone.
    COND_VB_SHOULD(VB_SILVER_COLLECT, CVAR_ENABLED && !IS_RANDO, {
        EnGSwitch* silver = va_arg(args, EnGSwitch*);

        if (*should && sState.trialActive && gPlayState != NULL && gPlayState->sceneNum == SCENE_KOKIRI_FOREST &&
            silver->switchFlag == SARIA_GAME_SILVER_FLAG) {
            SariaRupeeGame_OnRupeeCollected(gPlayState);
        }
    });

    // Backstop: even if Link somehow reaches the chest, it stays sealed until the trial is beaten.
    COND_VB_SHOULD(VB_OPEN_CHEST, CVAR_ENABLED && !IS_RANDO, {
        EnBox* chest = va_arg(args, EnBox*);

        if (gPlayState != NULL && gPlayState->sceneNum == SCENE_KOKIRI_FOREST &&
            (chest->dyna.actor.params & 0x1F) == SARIA_GAME_CHEST_FLAG && SariaRupeeGame_ShouldSealExist()) {
            *should = false;
            Notification::Emit({
                .prefix = "The chest is sealed",
                .message = "by Saria's magic",
                .remainingTime = 5.0f,
                .mute = true,
            });
        }
    });

    COND_HOOK(OnGameFrameUpdate, true, [&]() { SariaRupeeGame_OnFrameUpdate(); });
}

static void SariaRupeeGame_Register() {
    if (!SariaRupeeGame_IsEnabled()) {
        sState = SariaRupeeGameState();
    }

    SariaRupeeGame_RegisterTextHooks();
    SariaRupeeGame_RegisterGameplayHooks();
}

static RegisterShipInitFunc initFuncSariaRupeeGame(SariaRupeeGame_Register,
                                                   { CVAR_ENABLED_NAME, CVAR_RUPEE_COUNT_NAME, "IS_RANDO" });

// endregion
