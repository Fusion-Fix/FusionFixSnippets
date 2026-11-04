// Alien: Isolation: skip the save confirmation dialog
// Install: scripts\SkipSaveConfirmationDialog.cxx, with Ultimate ASI Loader 10.0.1 or newer as winmm.dll.
#include <injector/injector.hpp>
#include <Hooking.Patterns.h>

void Init()
{
    // The conditional jump in front of the dialog, made unconditional
    injector::WriteMemory<uint8_t>(hook::get_pattern("74 10 53 53 6A 1B"), 0xEB, true);
}
