/**
 * Fairy's Favor
 *
 * A custom ocarina song that calls a fairy to Link's side. Her favor opens the way to the Kokiri
 * Sword and lets him walk out of the Kokiri Shop with the Deku Shield without paying for it.
 * The shopkeeper notices soon after, and comes to collect.
 *
 * The song is recognized from the notes the ocarina reports, rather than by taking a slot in the
 * game's own song table, so no vanilla song is displaced and the sequence can be any length.
 */
#include <libultraship/bridge/consolevariablebridge.h>

#include <string>

#include "soh/cvar_prefixes.h"
#include "soh/Enhancements/custom-message/CustomMessageManager.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/Notification/Notification.h"
#include "soh/ShipInit.hpp"

extern "C" {
#include "z64.h"
#include "macros.h"
#include "variables.h"
#include "functions.h"
#include "overlays/actors/ovl_En_Elf/z_en_elf.h"
#include "overlays/actors/ovl_En_GirlA/z_en_girla.h"
#include "overlays/actors/ovl_En_Ossan/z_en_ossan.h"
extern PlayState* gPlayState;
}

#define CVAR_ENABLED_NAME CVAR_ENHANCEMENT("FairyFavor.Enabled")
#define CVAR_ENABLED CVarGetInteger(CVAR_ENABLED_NAME, 0)
#define CVAR_FREE_SHIELD_NAME CVAR_ENHANCEMENT("FairyFavor.FreeDekuShield")
#define CVAR_FREE_SHIELD CVarGetInteger(CVAR_FREE_SHIELD_NAME, 1)
#define CVAR_DEBT_NAME CVAR_ENHANCEMENT("FairyFavor.ShieldDebt")
#define CVAR_DEBT CVarGetInteger(CVAR_DEBT_NAME, 40)
#define CVAR_DEBT_DELAY_NAME CVAR_ENHANCEMENT("FairyFavor.DebtDelaySeconds")
#define CVAR_DEBT_DELAY CVarGetInteger(CVAR_DEBT_DELAY_NAME, 4)
#define CVAR_UNSEAL_NAME CVAR_ENHANCEMENT("FairyFavor.UnsealSwordChest")

#define TEXT_FAVOR_FAIRY 0x8F30
#define TEXT_FAVOR_FAIRY_AGAIN 0x8F31
#define TEXT_FAVOR_DEBT 0x8F32
#define TEXT_FAVOR_NO_RUPEES 0x8F33
#define TEXT_FAVOR_ADULT 0x8F34

// C-Up C-Up C-Right C-Right C-Down C-Down A. No song in gOcarinaSongButtons repeats a note, so
// nothing the player can already play reaches this sequence.
#define FAVOR_SONG_LENGTH 7

static const uint8_t sFavorSong[FAVOR_SONG_LENGTH] = {
    OCARINA_PITCH_D5, OCARINA_PITCH_D5, OCARINA_PITCH_A4, OCARINA_PITCH_A4,
    OCARINA_PITCH_F4, OCARINA_PITCH_F4, OCARINA_PITCH_D4,
};

#define FAVOR_FAIRY_FRAMES 300

struct FairyFavorState {
    uint8_t notes[FAVOR_SONG_LENGTH] = {};
    int32_t noteCount = 0;
    Actor* fairy = NULL;
    int32_t fairyFrames = 0;
    uint16_t pendingText = 0;
    Actor* pendingTextActor = NULL;
    int32_t debtTimer = 0;
};

static FairyFavorState sState;

// region helpers

static bool FairyFavor_IsEnabled() {
    return CVAR_ENABLED && !IS_RANDO;
}

static bool FairyFavor_HasFavor() {
    return Flags_GetInfTable(INFTABLE_FAIRY_FAVOR);
}

static bool FairyFavor_SongIsPlaying() {
    if (sState.noteCount < FAVOR_SONG_LENGTH) {
        return false;
    }

    for (int32_t i = 0; i < FAVOR_SONG_LENGTH; i++) {
        if (sState.notes[i] != sFavorSong[i]) {
            return false;
        }
    }

    return true;
}

// An Actor* is only safe to touch while it is still on one of the scene's lists. A fairy spawned
// as the player's child dies with him or with the scene, and either way the pointer goes stale.
static bool FairyFavor_ActorIsAlive(PlayState* play, Actor* target) {
    if (target == NULL) {
        return false;
    }

    for (int32_t list = 0; list < ACTORCAT_MAX; list++) {
        Actor* actor = play->actorCtx.actorLists[list].head;

        while (actor != NULL) {
            if (actor == target) {
                return true;
            }
            actor = actor->next;
        }
    }

    return false;
}

// Queues a textbox for a later frame. The song is still playing when it is recognized, and the
// ocarina owns the message context until it is put away.
static void FairyFavor_Say(uint16_t textId, Actor* actor) {
    sState.pendingText = textId;
    sState.pendingTextActor = actor;
}

// endregion

// region fairy

static Actor* FairyFavor_FindShopkeeper(PlayState* play) {
    Actor* actor = play->actorCtx.actorLists[ACTORCAT_NPC].head;

    while (actor != NULL) {
        if (actor->id == ACTOR_EN_OSSAN && actor->params == OSSAN_TYPE_KOKIRI) {
            return actor;
        }
        actor = actor->next;
    }

    return NULL;
}

static void FairyFavor_SummonFairy(PlayState* play) {
    Player* player = GET_PLAYER(play);

    if (player == NULL) {
        return;
    }

    // The Kokiri shop's own counter fairy is spawned this way. The FAIRY_KOKIRI action follows its
    // parent and kills itself without one, so the player is the only sensible parent to give it.
    Actor* fairy = Actor_SpawnAsChild(&play->actorCtx, &player->actor, play, ACTOR_EN_ELF, player->actor.world.pos.x,
                                      player->actor.world.pos.y, player->actor.world.pos.z, 0, 0, 0, FAIRY_KOKIRI);

    if (fairy == NULL) {
        return;
    }

    sState.fairy = fairy;
    sState.fairyFrames = FAVOR_FAIRY_FRAMES;
    Sfx_PlaySfxCentered(NA_SE_EV_FIATY_HEAL);
}

static void FairyFavor_UpdateFairy(PlayState* play) {
    if (sState.fairyFrames <= 0) {
        return;
    }

    if (!FairyFavor_ActorIsAlive(play, sState.fairy) || --sState.fairyFrames <= 0) {
        if (FairyFavor_ActorIsAlive(play, sState.fairy)) {
            Actor_Kill(sState.fairy);
        }
        sState.fairy = NULL;
        sState.fairyFrames = 0;
    }
}

// endregion

// region song

static void FairyFavor_OnSongPlayed(PlayState* play) {
    // Cleared either way, so holding the last note cannot trigger the song a second time.
    sState.noteCount = 0;

    if (play == NULL) {
        return;
    }

    if (LINK_IS_ADULT) {
        FairyFavor_Say(TEXT_FAVOR_ADULT, NULL);
        return;
    }

    if (FairyFavor_HasFavor()) {
        FairyFavor_SummonFairy(play);
        FairyFavor_Say(TEXT_FAVOR_FAIRY_AGAIN, NULL);
        return;
    }

    Flags_SetInfTable(INFTABLE_FAIRY_FAVOR);
    FairyFavor_SummonFairy(play);
    FairyFavor_Say(TEXT_FAVOR_FAIRY, NULL);

    Notification::Emit({
        .prefix = "The fairy's favor",
        .message = "the way to the Kokiri Sword is open",
        .remainingTime = 6.0f,
        .mute = true,
    });
}

static void FairyFavor_OnOcarinaNote(uint8_t note, float modulator, int8_t bend) {
    if (note == OCARINA_PITCH_NONE) {
        return;
    }

    for (int32_t i = 0; i < FAVOR_SONG_LENGTH - 1; i++) {
        sState.notes[i] = sState.notes[i + 1];
    }
    sState.notes[FAVOR_SONG_LENGTH - 1] = note;
    sState.noteCount++;

    if (FairyFavor_SongIsPlaying()) {
        FairyFavor_OnSongPlayed(gPlayState);
    }
}

// endregion

// region debt

// Takes the price of the shield out of Link's purse, or takes the shield back instead. The debt
// is a save flag, so leaving the shop before he arrives only postpones the conversation.
static void FairyFavor_Collect(PlayState* play) {
    Actor* shopkeeper = FairyFavor_FindShopkeeper(play);

    if (shopkeeper == NULL || play->msgCtx.msgMode != MSGMODE_NONE || Player_InCsMode(play)) {
        return;
    }

    int32_t debt = CVAR_DEBT;
    bool canPay = gSaveContext.rupees >= debt;

    Flags_UnsetInfTable(INFTABLE_FAIRY_SHIELD_DEBT);

    if (canPay) {
        Rupees_ChangeBy((s16)-debt);
        FairyFavor_Say(TEXT_FAVOR_DEBT, shopkeeper);
    } else {
        Inventory_DeleteEquipment(play, EQUIP_TYPE_SHIELD);
        FairyFavor_Say(TEXT_FAVOR_NO_RUPEES, shopkeeper);
    }

    Sfx_PlaySfxCentered(NA_SE_SY_ERROR);
}

// endregion

// region text

static void FairyFavor_ApplyMessage(uint16_t* textId, bool* loadFromMessageTable, const std::string& body) {
    CustomMessage msg;

    msg = CustomMessage(body);
    msg.AutoFormat();
    msg.LoadIntoFont();
    *loadFromMessageTable = false;
}

static void FairyFavor_FairyText(uint16_t* textId, bool* loadFromMessageTable) {
    FairyFavor_ApplyMessage(
        textId, loadFromMessageTable,
        "You called, and the forest answered.&I am only a small light, @, but small&lights know what is hidden.&"
        "The blade the Kokiri keep is south&west of here, behind the crawling&place in the rock. My favor is on it.");
}

static void FairyFavor_FairyAgainText(uint16_t* textId, bool* loadFromMessageTable) {
    FairyFavor_ApplyMessage(textId, loadFromMessageTable,
                            "Again? You already have all I can give, @.&South west, behind the rock. Go on.");
}

static void FairyFavor_DebtText(uint16_t* textId, bool* loadFromMessageTable) {
    FairyFavor_ApplyMessage(
        textId, loadFromMessageTable,
        "Hold it right there, @!&That shield walked out of my shop with&nothing left on the counter.&"
        "A fairy's word is not rupees, and my&shelf does not run on favors.");
}

static void FairyFavor_NoRupeesText(uint16_t* textId, bool* loadFromMessageTable) {
    FairyFavor_ApplyMessage(textId, loadFromMessageTable,
                            "Not a single rupee? Then the shield goes&back on the shelf, @.&"
                            "Come back with money and we will&forget this ever happened.");
}

static void FairyFavor_AdultText(uint16_t* textId, bool* loadFromMessageTable) {
    FairyFavor_ApplyMessage(textId, loadFromMessageTable,
                            "The notes hang in the air and nothing comes.&Whatever lived in that song stayed&"
                            "in the forest, behind you.");
}

// endregion

// region frame update

static void FairyFavor_OnFrameUpdate() {
    PlayState* play = gPlayState;

    if (play == NULL || !play->state.running) {
        return;
    }

    if (!FairyFavor_IsEnabled()) {
        sState = FairyFavorState();
        return;
    }

    FairyFavor_UpdateFairy(play);

    // Open whatever the song or the shopkeeper queued, once the message context is free.
    if (sState.pendingText != 0 && play->msgCtx.msgMode == MSGMODE_NONE && !Player_InCsMode(play)) {
        uint16_t textId = sState.pendingText;
        Actor* actor = FairyFavor_ActorIsAlive(play, sState.pendingTextActor) ? sState.pendingTextActor : NULL;

        sState.pendingText = 0;
        sState.pendingTextActor = NULL;
        Message_StartTextbox(play, textId, actor);
    }

    if (play->sceneNum != SCENE_KOKIRI_SHOP || !FairyFavor_HasFavor() ||
        !Flags_GetInfTable(INFTABLE_FAIRY_SHIELD_DEBT)) {
        return;
    }

    // A short grace period, so he catches Link in the doorway rather than at the counter.
    if (sState.debtTimer > 0) {
        sState.debtTimer--;
        return;
    }

    FairyFavor_Collect(play);
}

// endregion

// region hooks

static void FairyFavor_RegisterHooks() {
    bool enabled = CVAR_ENABLED && !IS_RANDO;

    COND_HOOK(OnOcarinaNote, enabled, FairyFavor_OnOcarinaNote);

    // The Deku Shield costs nothing while the fairy's favor is on it.
    COND_ID_HOOK(OnActorInit, ACTOR_EN_GIRLA, enabled && CVAR_FREE_SHIELD, [](void* actorPtr) {
        PlayState* play = gPlayState;
        EnGirlA* item = (EnGirlA*)actorPtr;

        if (play == NULL || play->sceneNum != SCENE_KOKIRI_SHOP || !FairyFavor_HasFavor() || LINK_IS_ADULT) {
            return;
        }

        if (item->getItemId == GI_SHIELD_DEKU) {
            item->basePrice = 0;
        }
    });

    // Walking out with it is the easy part. OnSaleEnd is only dispatched to unfiltered hooks, so
    // the item is checked here rather than through a filtered hook that would never be called.
    COND_HOOK(OnSaleEnd, enabled && CVAR_FREE_SHIELD, [](GetItemEntry itemEntry) {
        PlayState* play = gPlayState;

        if (itemEntry.getItemId != GI_SHIELD_DEKU) {
            return;
        }

        if (play == NULL || play->sceneNum != SCENE_KOKIRI_SHOP || !FairyFavor_HasFavor()) {
            return;
        }

        int32_t delay = CVAR_DEBT_DELAY;

        Flags_SetInfTable(INFTABLE_FAIRY_SHIELD_DEBT);
        sState.debtTimer = CLAMP(delay, 0, 60) * 20;
    });

    COND_ID_HOOK(OnOpenText, TEXT_FAVOR_FAIRY, true, FairyFavor_FairyText);
    COND_ID_HOOK(OnOpenText, TEXT_FAVOR_FAIRY_AGAIN, true, FairyFavor_FairyAgainText);
    COND_ID_HOOK(OnOpenText, TEXT_FAVOR_DEBT, true, FairyFavor_DebtText);
    COND_ID_HOOK(OnOpenText, TEXT_FAVOR_NO_RUPEES, true, FairyFavor_NoRupeesText);
    COND_ID_HOOK(OnOpenText, TEXT_FAVOR_ADULT, true, FairyFavor_AdultText);

    COND_HOOK(OnGameFrameUpdate, true, [&]() { FairyFavor_OnFrameUpdate(); });
}

static void FairyFavor_Register() {
    if (!FairyFavor_IsEnabled()) {
        sState = FairyFavorState();
    }

    FairyFavor_RegisterHooks();
}

static RegisterShipInitFunc initFuncFairyFavor(FairyFavor_Register,
                                               { CVAR_ENABLED_NAME, CVAR_FREE_SHIELD_NAME, CVAR_DEBT_NAME,
                                                 CVAR_DEBT_DELAY_NAME, CVAR_UNSEAL_NAME, "IS_RANDO" });

// endregion
