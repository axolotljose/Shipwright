/**
 * Sprint
 *
 * Hold a button to run faster.
 *
 * The run speed target is multiplied where z_player asks permission to change it, and the caller
 * feeds that target straight into func_8083DF68, which steps linearVelocity toward it without
 * clamping. The hook deliberately leaves the result alone so vanilla still applies it, which means
 * this stacks with the existing Speed Modifier cheat rather than replacing it.
 */
#include <libultraship/bridge/consolevariablebridge.h>

#include "soh/cvar_prefixes.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/OTRGlobals.h"
#include "soh/ShipInit.hpp"

extern "C" {
#include "z64.h"
#include "macros.h"
#include "variables.h"
extern PlayState* gPlayState;
}

#define CVAR_ENABLED_NAME CVAR_ENHANCEMENT("Sprint.Enabled")
#define CVAR_ENABLED CVarGetInteger(CVAR_ENABLED_NAME, 0)
#define CVAR_BUTTON_NAME CVAR_ENHANCEMENT("Sprint.Button")
#define CVAR_BUTTON CVarGetInteger(CVAR_BUTTON_NAME, BTN_CUSTOM_MODIFIER1)
#define CVAR_SPEED_NAME CVAR_ENHANCEMENT("Sprint.SpeedMultiplier")
#define CVAR_SPEED CVarGetFloat(CVAR_SPEED_NAME, 1.5f)

// The hook only ever runs from the grounded walk action, so swimming, crawling, riding and
// Z-targeting a hostile are already excluded by where the game asks. What is left to check is
// that Link is actually moving somewhere, and that the button is down.
static bool Sprint_IsSprinting(f32 speedTarget) {
    u32 button = (u32)CVAR_BUTTON;

    if (speedTarget <= 0.0f || button == 0 || gPlayState == NULL) {
        return false;
    }

    return CHECK_BTN_ALL(gPlayState->state.input[0].cur.button, button);
}

static void Sprint_RegisterHooks() {
    COND_VB_SHOULD(VB_PLAYER_MODIFY_RUN_SPEED, CVAR_ENABLED, {
        [[maybe_unused]] Player* player = va_arg(args, Player*);
        f32* speedTarget = va_arg(args, f32*);

        if (speedTarget != NULL && Sprint_IsSprinting(*speedTarget)) {
            *speedTarget *= CVAR_SPEED;
        }
    });
}

static RegisterShipInitFunc initFuncSprint(Sprint_RegisterHooks,
                                           { CVAR_ENABLED_NAME, CVAR_BUTTON_NAME, CVAR_SPEED_NAME });
