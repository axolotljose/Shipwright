#include "LilithWhiteRose.h"
#include "z64cutscene_commands.h"

/**
 * Cutscenes for the Lilith, the White Rose Princess quest.
 *
 * All three use the same shape: a camera that swings around Link (relative to him, so the
 * scripts work anywhere in the scene), a textbox that pauses playback until the player advances
 * it, then a terminator with INVALID_DESTINATION_0 so nothing is warped or loaded afterwards.
 *
 * Frame counts are matched between the camera lists, the text window and CS_BEGIN_CUTSCENE's
 * end frame. Camera points are keyframed like the vanilla scripts: every point but the last
 * uses CS_CMD_CONTINUE and the final one uses CS_CMD_STOP.
 */

// clang-format off

// Meeting Lilith for the first time inside the Deku Tree.
CutsceneData gLilithIntroCs[] = {
    CS_BEGIN_CUTSCENE(4, 210),
    CS_CAM_EYE_REL_TO_PLAYER_LIST(0, 210),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 60.0f, -110, 60, 150, 0x0000),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 60.0f, -40, 50, 130, 0x006E),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_STOP,     0x00, 0, 60.0f, 40, 40, 120, 0x00D2),
    CS_CAM_AT_REL_TO_PLAYER_LIST(0, 210),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 60.0f, 0, 50, 0, 0x0000),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 60.0f, 0, 45, 0, 0x006E),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_STOP,     0x00, 0, 60.0f, 0, 40, 0, 0x00D2),
    CS_TEXT_LIST(1),
        CS_TEXT_DISPLAY_TEXTBOX(TEXT_LILITH_INTRO, 5, 200, 0, 0xFFFF, 0xFFFF),
    CS_TERMINATOR(INVALID_DESTINATION_0, 205, 210),
    CS_END(),
};

// Agreeing to the trial.
CutsceneData gLilithAcceptCs[] = {
    CS_BEGIN_CUTSCENE(4, 200),
    CS_CAM_EYE_REL_TO_PLAYER_LIST(0, 200),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 55.0f, 60, 120, 120, 0x0000),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_STOP,     0x00, 0, 55.0f, 0, 180, 160, 0x00C8),
    CS_CAM_AT_REL_TO_PLAYER_LIST(0, 200),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 55.0f, 0, 40, 0, 0x0000),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_STOP,     0x00, 0, 55.0f, 0, 60, 0, 0x00C8),
    CS_TEXT_LIST(1),
        CS_TEXT_DISPLAY_TEXTBOX(TEXT_LILITH_ACCEPT, 5, 190, 0, 0xFFFF, 0xFFFF),
    CS_TERMINATOR(INVALID_DESTINATION_0, 195, 200),
    CS_END(),
};

// Beating the wave outside the tree: the sword blessing.
CutsceneData gLilithVictoryCs[] = {
    CS_BEGIN_CUTSCENE(4, 230),
    CS_CAM_EYE_REL_TO_PLAYER_LIST(0, 230),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 50.0f, 0, 220, 220, 0x0000),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 50.0f, 90, 90, 130, 0x0078),
        CS_CAM_EYE_REL_TO_PLAYER(CS_CMD_STOP,     0x00, 0, 50.0f, 0, 45, 110, 0x00E6),
    CS_CAM_AT_REL_TO_PLAYER_LIST(0, 230),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 50.0f, 0, 40, 0, 0x0000),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_CONTINUE, 0x00, 0, 50.0f, 0, 40, 0, 0x0078),
        CS_CAM_AT_REL_TO_PLAYER(CS_CMD_STOP,     0x00, 0, 50.0f, 0, 45, 0, 0x00E6),
    CS_TEXT_LIST(1),
        CS_TEXT_DISPLAY_TEXTBOX(TEXT_LILITH_VICTORY, 5, 220, 0, 0xFFFF, 0xFFFF),
    CS_TERMINATOR(INVALID_DESTINATION_0, 225, 230),
    CS_END(),
};

// clang-format on
