#ifndef LILITH_WHITE_ROSE_H
#define LILITH_WHITE_ROSE_H

#include "z64.h"

/**
 * Shared by LilithWhiteRose.cpp (gameplay) and LilithWhiteRoseCutscenes.c (cutscene scripts).
 *
 * The scripts have to live in a C file: the CS_* macros emit constants such as 0xFFFFFFFF,
 * which C++ rejects as a narrowing conversion inside a braced initializer list. Every vanilla
 * cutscene script in the decomp is a .c file for the same reason.
 */

// Text ids used by this mod. They sit outside every table shipped with the game and are only
// ever opened through the OnOpenText hooks, which always supply a custom message.
#define TEXT_LILITH_INTRO 0x8F20
#define TEXT_LILITH_OFFER 0x8F21
#define TEXT_LILITH_ACCEPT 0x8F22
#define TEXT_LILITH_VICTORY 0x8F23
#define TEXT_LILITH_REMINDER 0x8F24

extern CutsceneData gLilithIntroCs[];
extern CutsceneData gLilithAcceptCs[];
extern CutsceneData gLilithVictoryCs[];

#endif
