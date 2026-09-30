/**
 * Lilith, the White Rose Princess
 *
 * A Deku Tree quest NPC. Lilith appears in the main chamber of the Deku Tree and offers Link a
 * trial: step outside and defeat a wave of enemies without losing all three of his starting
 * hearts. Succeed and she blesses the Kokiri Sword, then vanishes for good.
 *
 * Flow
 * 1. Entering the Deku Tree as child Link spawns Lilith (once per visit, while the trial is
 *    still open). Talking to her plays an intro cutscene with her dialogue.
 * 2. Talking again offers the trial. Accepting plays a second cutscene and marks the trial as
 *    accepted.
 * 3. Stepping out into Kokiri Forest with the trial accepted spawns the enemy wave around Link.
 *    Every kill is counted; if Link dies the trial fails and can be attempted again.
 * 4. Clearing the wave plays a victory cutscene, sets INFTABLE_LILITH_TRIAL_COMPLETE, and from
 *    then on Lilith never spawns again.
 * 5. While the trial is complete, the Kokiri Sword hits with the Master Sword's damage type,
 *    which every enemy damage table in the game already understands.
 *
 * Implementation notes
 * - Lilith is a custom actor registered through ActorDB. Shipwright has no custom model format,
 *   so she reuses the child Zelda object (OBJECT_ZL4): a rigged, animated princess that is
 *   already in the game. Swapping in a bespoke model later only means changing the object id
 *   and the skeleton/animation symbols below.
 * - The cutscenes are hand authored CutsceneData scripts, the same format every vanilla scene
 *   cutscene uses, driven by setting play->csCtx.segment and gSaveContext.cutsceneTrigger.
 * - Neither the Deku Tree nor Kokiri Forest geometry is hardcoded: Lilith and the enemies are
 *   placed with a floor raycast relative to Link.
 *
 * The mod disables itself while a randomizer seed is running, because changing the Kokiri
 * Sword's damage would break seed balance and the Deku Tree is a starting area.
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
#include "z64cutscene_commands.h"
#include "objects/object_zl4/object_zl4.h"
#include "soh/Enhancements/CustomQuests/LilithWhiteRose.h"

extern PlayState* gPlayState;
extern SaveContext gSaveContext;
}

#define LILITH_DEFAULT_ENEMY_COUNT 6
#define LILITH_DEFAULT_SPAWN_DISTANCE 200
#define LILITH_MAX_ENEMIES 10
#define LILITH_TALK_RANGE 100.0f

#define CVAR_ENABLED_NAME CVAR_ENHANCEMENT("Lilith.Enabled")
#define CVAR_ENABLED CVarGetInteger(CVAR_ENABLED_NAME, 0)
#define CVAR_ENEMY_COUNT_NAME CVAR_ENHANCEMENT("Lilith.EnemyCount")
#define CVAR_ENEMY_COUNT CVarGetInteger(CVAR_ENEMY_COUNT_NAME, LILITH_DEFAULT_ENEMY_COUNT)
#define CVAR_SPAWN_DISTANCE_NAME CVAR_ENHANCEMENT("Lilith.SpawnDistance")
#define CVAR_SPAWN_DISTANCE CVarGetInteger(CVAR_SPAWN_DISTANCE_NAME, LILITH_DEFAULT_SPAWN_DISTANCE)

enum LilithCutscene {
    LILITH_CS_NONE,
    LILITH_CS_INTRO,
    LILITH_CS_ACCEPT,
    LILITH_CS_VICTORY,
};

struct LilithState {
    LilithCutscene playingCs = LILITH_CS_NONE;
    bool csStarted = false;
    int32_t csWaitFrames = 0;
    bool challengeAccepted = false;
    bool waveSpawned = false;
    int32_t waveRemaining = 0;
    int32_t spawnAttempts = 0;
    bool victoryPending = false;
};

static LilithState sState;
static Actor* sWaveActors[LILITH_MAX_ENEMIES];
static int32_t sLilithActorId = -1;

// region helpers

static bool Lilith_IsEnabled() {
    return CVAR_ENABLED && !IS_RANDO;
}

static bool Lilith_IsTrialComplete() {
    return Flags_GetInfTable(INFTABLE_LILITH_TRIAL_COMPLETE);
}

// Starts a hand authored cutscene. The engine picks the trigger up on the following frame in
// func_80068ECC, which is why the caller then waits for csCtx.state to return to IDLE.
static void Lilith_PlayCutscene(PlayState* play, LilithCutscene which) {
    CutsceneData* script = nullptr;

    switch (which) {
        case LILITH_CS_INTRO:
            script = gLilithIntroCs;
            break;
        case LILITH_CS_ACCEPT:
            script = gLilithAcceptCs;
            break;
        case LILITH_CS_VICTORY:
            script = gLilithVictoryCs;
            break;
        default:
            return;
    }

    if (play->csCtx.state != CS_STATE_IDLE || Player_InCsMode(play)) {
        return;
    }

    play->csCtx.segment = script;
    gSaveContext.cutsceneTrigger = 1;
    sState.playingCs = which;
    sState.csStarted = false;
    sState.csWaitFrames = 0;
}

static void Lilith_FinishCutscene() {
    switch (sState.playingCs) {
        case LILITH_CS_INTRO:
            Flags_SetInfTable(INFTABLE_LILITH_MET);
            break;
        case LILITH_CS_ACCEPT:
            Notification::Emit({
                .prefix = "Lilith's trial",
                .message = "begins outside",
                .remainingTime = 4.0f,
                .mute = true,
            });
            break;
        default:
            break;
    }
    sState.playingCs = LILITH_CS_NONE;
}

// The engine flips csCtx.state out of IDLE a frame or two after the trigger is set, so a
// cutscene is only treated as finished once it has actually been seen running. The frame
// timeout keeps a trigger that never took off (another cutscene won) from hanging the quest.
static bool Lilith_UpdateCutscene(PlayState* play) {
    if (sState.playingCs == LILITH_CS_NONE) {
        return false;
    }

    if (play->csCtx.state != CS_STATE_IDLE) {
        sState.csStarted = true;
    } else if (sState.csStarted || ++sState.csWaitFrames > 20) {
        sState.csStarted = false;
        sState.csWaitFrames = 0;
        Lilith_FinishCutscene();
    }

    return true;
}

// endregion

// region Lilith actor

typedef struct Lilith {
    /* 0x000 */ Actor actor;
    /* 0x14C */ SkelAnime skelAnime;
    /* 0x190 */ Vec3s jointTable[18];
    /* 0x1F8 */ Vec3s morphTable[18];
    /* 0x260 */ s16 talkPhase;
} Lilith;

static void LilithNpc_Init(Actor* actor, PlayState* play) {
    Lilith* self = (Lilith*)actor;

    ActorShape_Init(&actor->shape, 0.0f, ActorShadow_DrawCircle, 24.0f);
    SkelAnime_InitFlex(play, &self->skelAnime, (FlexSkeletonHeader*)&gChildZeldaSkel, NULL, self->jointTable,
                       self->morphTable, 18);
    Animation_PlayLoop(&self->skelAnime, (AnimationHeader*)&gChildZeldaAnim_000654);

    actor->scale.x = actor->scale.y = actor->scale.z = 0.01f;
    actor->targetMode = 6;
    actor->gravity = 0.0f;
    actor->flags |= ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY;
    self->talkPhase = 0;

    Sfx_PlaySfxCentered(NA_SE_EV_FIATY_HEAL);
}

static void LilithNpc_Destroy(Actor* actor, PlayState* play) {
}

static void LilithNpc_Update(Actor* actor, PlayState* play) {
    Lilith* self = (Lilith*)actor;

    SkelAnime_Update(&self->skelAnime);

    // A cutscene owns the camera and the input while it runs.
    if (sState.playingCs != LILITH_CS_NONE) {
        return;
    }

    // Waiting for Link to close the trial offer, which is what starts the trial.
    if (self->talkPhase == 3) {
        if (play->msgCtx.msgMode == MSGMODE_NONE) {
            self->talkPhase = 0;
            sState.challengeAccepted = true;
            Lilith_PlayCutscene(play, LILITH_CS_ACCEPT);
        }
        return;
    }

    // Any other dialogue has exclusive control while it is up.
    if (play->msgCtx.msgMode != MSGMODE_NONE) {
        return;
    }

    if (Actor_ProcessTalkRequest(actor, play)) {
        self->talkPhase = 1;
        return;
    }

    if (self->talkPhase == 1) {
        self->talkPhase = 2;
        return;
    }

    if (self->talkPhase == 2) {
        self->talkPhase = 0;

        if (!Flags_GetInfTable(INFTABLE_LILITH_MET)) {
            Lilith_PlayCutscene(play, LILITH_CS_INTRO);
        } else if (sState.challengeAccepted) {
            Message_StartTextbox(play, TEXT_LILITH_REMINDER, actor);
        } else {
            Message_StartTextbox(play, TEXT_LILITH_OFFER, actor);
            self->talkPhase = 3;
        }
        return;
    }

    Actor_OfferTalk(actor, play, LILITH_TALK_RANGE);
}

static void LilithNpc_Draw(Actor* actor, PlayState* play) {
    Lilith* self = (Lilith*)actor;

    SkelAnime_DrawSkeletonOpa(play, &self->skelAnime, NULL, NULL, actor);
}

static void LilithNpc_RegisterActor() {
    if (sLilithActorId >= 0) {
        return;
    }

    ActorDBInit init = {
        .name = "LilithWhiteRose",
        .desc = "Lilith, the White Rose Princess",
        .id = -1,
        .category = ACTORCAT_NPC,
        .flags = ACTOR_FLAG_ATTENTION_ENABLED | ACTOR_FLAG_FRIENDLY,
        .objectId = OBJECT_ZL4,
        .instanceSize = sizeof(Lilith),
        .init = LilithNpc_Init,
        .destroy = LilithNpc_Destroy,
        .update = LilithNpc_Update,
        .draw = LilithNpc_Draw,
        .reset = nullptr,
    };

    sLilithActorId = ActorDB::Instance->AddEntry(init).entry.id;
}

// endregion

// region spawning

static bool Lilith_FindSpawnPoint(PlayState* play, Vec3f* out, f32 distance, f32 minClearance) {
    Player* player = GET_PLAYER(play);
    s16 angle;
    f32 radius;
    CollisionPoly* floorPoly = NULL;
    Vec3f probe;
    f32 floorY;
    int32_t i;

    if (player == NULL) {
        return false;
    }

    for (i = 0; i < 24; i++) {
        angle = (s16)(Rand_ZeroOne() * 65536.0f);
        radius = distance + (Rand_ZeroOne() - 0.5f) * 120.0f;

        probe.x = player->actor.world.pos.x + radius * Math_SinS(angle);
        probe.y = player->actor.world.pos.y + 300.0f;
        probe.z = player->actor.world.pos.z + radius * Math_CosS(angle);

        floorY = BgCheck_EntityRaycastFloor1(&play->colCtx, &floorPoly, &probe);
        if (floorPoly == NULL || floorY <= BGCHECK_Y_MIN) {
            continue; // off the edge or under nothing
        }
        if (fabsf(floorY - player->actor.world.pos.y) > 250.0f) {
            continue; // a different level of the room
        }
        if (Math_Vec3f_DistXZ(&probe, &player->actor.world.pos) < minClearance) {
            continue; // too close to Link
        }

        out->x = probe.x;
        out->y = floorY;
        out->z = probe.z;
        return true;
    }

    return false;
}

static Actor* Lilith_FindLilith(PlayState* play) {
    if (sLilithActorId < 0) {
        return NULL;
    }

    return Actor_Find(&play->actorCtx, sLilithActorId, ACTORCAT_NPC);
}

static void Lilith_SpawnNpc(PlayState* play) {
    Vec3f pos;
    f32 distance = CLAMP((f32)CVAR_SPAWN_DISTANCE, 60.0f, 600.0f);

    if (!Lilith_FindSpawnPoint(play, &pos, distance, 100.0f)) {
        sState.spawnAttempts++;
        return;
    }

    LilithNpc_RegisterActor();
    if (sLilithActorId < 0) {
        return;
    }

    if (Actor_Spawn(&play->actorCtx, play, sLilithActorId, pos.x, pos.y, pos.z, 0, 0, 0, 0) != NULL) {
        sState.spawnAttempts = 0;
    }
}

// Enemies, easy first: Deku Babas, Skulltulas, Tektites, Torch Slugs, then Biris.
static const s16 sWaveEnemyIds[LILITH_MAX_ENEMIES] = {
    ACTOR_EN_DEKUBABA, ACTOR_EN_DEKUBABA, ACTOR_EN_ST,    ACTOR_EN_ST,   ACTOR_EN_TITE,
    ACTOR_EN_TITE,     ACTOR_EN_TORCH,    ACTOR_EN_TORCH, ACTOR_EN_BILI, ACTOR_EN_BILI,
};

static void Lilith_SpawnWave(PlayState* play) {
    int32_t count = CLAMP(CVAR_ENEMY_COUNT, 1, LILITH_MAX_ENEMIES);
    int32_t spawned = 0;
    int32_t i;

    for (i = 0; i < LILITH_MAX_ENEMIES; i++) {
        sWaveActors[i] = NULL;
    }

    for (i = 0; i < count; i++) {
        Vec3f pos;

        if (!Lilith_FindSpawnPoint(play, &pos, 260.0f + (i % 3) * 90.0f, 140.0f)) {
            continue;
        }

        sWaveActors[i] = Actor_Spawn(&play->actorCtx, play, sWaveEnemyIds[i], pos.x, pos.y, pos.z, 0, 0, 0, 0);
        if (sWaveActors[i] != NULL) {
            spawned++;
        }
    }

    if (spawned == 0) {
        Notification::Emit({
            .prefix = "Lilith's trial",
            .message = "could not find room here",
            .remainingTime = 4.0f,
            .mute = true,
        });
        sState.challengeAccepted = false;
        return;
    }

    sState.waveSpawned = true;
    sState.waveRemaining = spawned;
    Audio_PlaySoundTransposed(&gSfxDefaultPos, NA_SE_EN_WOLFOS_APPEAR, 0);
    Notification::Emit({
        .prefix = "Lilith's trial",
        .message = "defeat " + std::to_string(spawned) + " enemies",
        .remainingTime = 4.0f,
        .mute = true,
    });
}

// A recorded Actor* is only safe to touch while it is still linked into one of the actor
// lists. Leaving Kokiri Forest frees the wave, so every pointer is validated before use.
static bool Lilith_ActorIsAlive(PlayState* play, Actor* target) {
    int32_t cat;

    if (target == NULL) {
        return false;
    }

    for (cat = 0; cat < ACTORCAT_MAX; cat++) {
        Actor* actor = play->actorCtx.actorLists[cat].head;

        while (actor != NULL) {
            if (actor == target) {
                return true;
            }
            actor = actor->next;
        }
    }

    return false;
}

// Kills whatever is still alive and forgets the rest. Also used to resync the counter after an
// enemy is removed by something other than Link's sword.
static int32_t Lilith_CountWaveAlive(PlayState* play) {
    int32_t alive = 0;
    int32_t i;

    for (i = 0; i < LILITH_MAX_ENEMIES; i++) {
        if (sWaveActors[i] == NULL) {
            continue;
        }
        if (Lilith_ActorIsAlive(play, sWaveActors[i])) {
            alive++;
        } else {
            sWaveActors[i] = NULL;
        }
    }

    return alive;
}

static void Lilith_ClearWave(PlayState* play) {
    int32_t i;

    for (i = 0; i < LILITH_MAX_ENEMIES; i++) {
        if (Lilith_ActorIsAlive(play, sWaveActors[i])) {
            Actor_Kill(sWaveActors[i]);
        }
        sWaveActors[i] = NULL;
    }

    sState.waveSpawned = false;
    sState.waveRemaining = 0;
}

// Drops the wave bookkeeping without touching any actor: the scene that owned them is gone.
static void Lilith_ForgetWave() {
    int32_t i;

    for (i = 0; i < LILITH_MAX_ENEMIES; i++) {
        sWaveActors[i] = NULL;
    }

    sState.waveSpawned = false;
    sState.waveRemaining = 0;
}

// endregion

// region trial progress

static void Lilith_CompleteTrial(PlayState* play) {
    if (Lilith_IsTrialComplete()) {
        return;
    }

    Flags_SetInfTable(INFTABLE_LILITH_TRIAL_COMPLETE);
    // The wave is empty by the time this runs, so only the bookkeeping is dropped.
    Lilith_ForgetWave();
    sState.victoryPending = true;
    sState.challengeAccepted = false;

    Sfx_PlaySfxCentered(NA_SE_SY_CORRECT_CHIME);
    Notification::Emit({
        .prefix = "Kokiri Sword",
        .message = "blessed by the White Rose",
        .remainingTime = 6.0f,
        .mute = true,
    });
}

static void Lilith_FailTrial(PlayState* play) {
    Lilith_ClearWave(play);
    sState.challengeAccepted = false;

    Notification::Emit({
        .prefix = "Lilith's trial",
        .message = "failed - speak to her again",
        .remainingTime = 5.0f,
        .mute = true,
    });
}

// endregion

// region text

static void Lilith_ApplyMessage(uint16_t* textId, bool* loadFromMessageTable, const std::string& body) {
    CustomMessage msg;

    msg = CustomMessage(body);
    msg.AutoFormat();
    msg.LoadIntoFont();
    *loadFromMessageTable = false;
}

static void Lilith_IntroText(uint16_t* textId, bool* loadFromMessageTable) {
    Lilith_ApplyMessage(textId, loadFromMessageTable,
                        "You are brave to walk so far into my tree, @.&I am Lilith, princess of the white rose.&"
                        "The forest has been waiting for someone&with a sword in their hand.");
}

static void Lilith_OfferText(uint16_t* textId, bool* loadFromMessageTable) {
    Lilith_ApplyMessage(textId, loadFromMessageTable,
                        "Your Kokiri Sword is honest, but small.&Prove your heart is larger.&"
                        "Step outside my tree and cut down every&monster the forest sends at you.&"
                        "You may be wounded, but do not fall.&Do this, and the blade will remember it.");
}

static void Lilith_AcceptText(uint16_t* textId, bool* loadFromMessageTable) {
    Lilith_ApplyMessage(textId, loadFromMessageTable,
                        "Then go. The forest is already stirring.&I will be waiting here among the roots.");
}

static void Lilith_VictoryText(uint16_t* textId, bool* loadFromMessageTable) {
    Lilith_ApplyMessage(textId, loadFromMessageTable,
                        "Every one of them, and still standing.&The white rose remembers a promise like that.&"
                        "Your sword carries my blessing now - it will&cut as deep as the Master Sword itself.&"
                        "Go on, little knight. My work is done.");
}

static void Lilith_ReminderText(uint16_t* textId, bool* loadFromMessageTable) {
    Lilith_ApplyMessage(textId, loadFromMessageTable,
                        "The forest is still out there, @.&Step outside and finish what we began.");
}

// endregion

// region frame update

static void Lilith_OnFrameUpdate() {
    PlayState* play = gPlayState;

    if (play == NULL || !play->state.running) {
        return;
    }

    bool inDekuTree = play->sceneNum == SCENE_DEKU_TREE;
    bool inKokiri = play->sceneNum == SCENE_KOKIRI_FOREST;

    // Always registered, so disabling the mod still cleans up after it.
    if (!Lilith_IsEnabled()) {
        if (inDekuTree) {
            Actor* lilith = Lilith_FindLilith(play);
            if (lilith != NULL) {
                Actor_Kill(lilith);
            }
        }
        if (inKokiri && sState.waveSpawned) {
            Lilith_ClearWave(play);
        }
        sState.playingCs = LILITH_CS_NONE;
        sState.victoryPending = false;
        return;
    }

    // Cutscene bookkeeping is scene independent: the intro runs in the Deku Tree, the victory
    // scene runs in Kokiri Forest.
    Lilith_UpdateCutscene(play);

    // Adult Link never meets her, and she is gone for good once the trial is beaten.
    bool lilithShouldExist = inDekuTree && !LINK_IS_ADULT && !Lilith_IsTrialComplete();

    if (inDekuTree) {
        if (lilithShouldExist) {
            if (Lilith_FindLilith(play) == NULL) {
                if (sState.spawnAttempts < 300) {
                    Lilith_SpawnNpc(play);
                }
            }
        } else {
            Actor* lilith = Lilith_FindLilith(play);
            if (lilith != NULL) {
                Actor_Kill(lilith);
            }
        }
    }

    if (inKokiri) {
        if (sState.victoryPending) {
            sState.victoryPending = false;
            Lilith_PlayCutscene(play, LILITH_CS_VICTORY);
            return;
        }

        if (sState.challengeAccepted && !sState.waveSpawned && !Lilith_IsTrialComplete() &&
            play->msgCtx.msgMode == MSGMODE_NONE) {
            Lilith_SpawnWave(play);
        }

        if (sState.waveSpawned) {
            sState.waveRemaining = Lilith_CountWaveAlive(play);

            if (sState.waveRemaining <= 0) {
                // The victory cutscene itself is started by the victoryPending branch, which
                // runs ahead of this block on the following frame.
                Lilith_CompleteTrial(play);
            } else if (gSaveContext.health <= 0) {
                Lilith_FailTrial(play);
            }
        }
    } else {
        // Anywhere else the wave actors no longer exist, so only the bookkeeping is dropped.
        if (sState.waveSpawned) {
            Lilith_ForgetWave();
            sState.challengeAccepted = false;
        }
    }
}

// endregion

// region hooks

static void Lilith_OnPlayerUpdate(void* actorPtr) {
    Player* player = (Player*)actorPtr;
    int32_t i;

    if (!Lilith_IsTrialComplete()) {
        return;
    }

    // The Kokiri Sword attacks with DMG_SLASH_KOKIRI, which every damage table scores as 1.
    // Replacing that bit with DMG_SLASH_MASTER makes the blessed blade score as 2 everywhere
    // without touching a single damage table.
    for (i = 0; i < 2; i++) {
        u32* dmgFlags = &player->meleeWeaponQuads[i].info.toucher.dmgFlags;

        if (*dmgFlags & DMG_SLASH_KOKIRI) {
            *dmgFlags = (*dmgFlags & ~DMG_SLASH_KOKIRI) | DMG_SLASH_MASTER;
        }
    }
}

static void Lilith_RegisterHooks() {
    COND_ID_HOOK(OnOpenText, TEXT_LILITH_INTRO, true, Lilith_IntroText);
    COND_ID_HOOK(OnOpenText, TEXT_LILITH_OFFER, true, Lilith_OfferText);
    COND_ID_HOOK(OnOpenText, TEXT_LILITH_ACCEPT, true, Lilith_AcceptText);
    COND_ID_HOOK(OnOpenText, TEXT_LILITH_VICTORY, true, Lilith_VictoryText);
    COND_ID_HOOK(OnOpenText, TEXT_LILITH_REMINDER, true, Lilith_ReminderText);

    COND_ID_HOOK(OnActorUpdate, ACTOR_PLAYER, CVAR_ENABLED && !IS_RANDO, Lilith_OnPlayerUpdate);

    COND_HOOK(OnGameFrameUpdate, true, [&]() { Lilith_OnFrameUpdate(); });
}

static void Lilith_Register() {
    if (!Lilith_IsEnabled()) {
        sState = LilithState();
    }

    Lilith_RegisterHooks();
}

static RegisterShipInitFunc initFuncLilithWhiteRose(Lilith_Register,
                                                    { CVAR_ENABLED_NAME, CVAR_ENEMY_COUNT_NAME, "IS_RANDO" });

// endregion
