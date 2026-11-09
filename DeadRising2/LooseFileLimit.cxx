// Dead Rising 2: no startup crash with many unpacked files
// At startup the game lists every loose file below data\ in a table made for 2048 files. With more files (unpacked
// archives, or an update\ folder, which Ultimate ASI Loader 10 shows inside data\) it writes past the end of the
// table and crashes. This makes the table grow as needed, so every file stays listed.
// Made for deadrising2.exe from Steam; with another exe the loader reports a missing pattern and nothing changes.
// Install: scripts\LooseFileLimit.cxx, with Ultimate ASI Loader 10.0.1 or newer as dinput8.dll.
#include <cstdint>
#include <cstring>
#include <safetyhook.hpp>
#include <Hooking.Patterns.h>

struct FileInfo
{
    uint32_t hash;
    uint32_t size;
    uint32_t writeTimeLow;
    uint32_t writeTimeHigh;
};

struct FileIndex
{
    uint32_t hash;
    int32_t info;
};

// The game's file info cache: the file list and a sorted index into it
struct FileInfoCache
{
    FileInfo* infos;     // +0x00
    int32_t numInfos;    // +0x04
    int32_t maxInfos;    // +0x08
    int32_t numIndex;    // +0x0C
    int32_t maxIndex;    // +0x10
    uint8_t indexSorted; // +0x14
    FileIndex* index;    // +0x18
};
static_assert(sizeof(FileInfoCache) == 0x1C, "FileInfoCache");

// Both are __thiscall methods of the cache
typedef FileInfoCache*(__fastcall* Create_t)(FileInfoCache* self, void* edx, uint32_t maxInfos);
typedef void(__fastcall* Release_t)(FileInfoCache* self, void* edx);

Create_t createCache = nullptr;
Release_t releaseCache = nullptr;
SafetyHookMid overflowHook{};

uintptr_t FollowCall(void* call)
{
    return (uintptr_t)call + 5 + *(int32_t*)((uintptr_t)call + 1);
}

// Moves the lists into arrays twice the size, made and freed by the game's own allocator
void Grow(FileInfoCache* cache)
{
    FileInfoCache bigger{};
    createCache(&bigger, nullptr, (uint32_t)cache->maxInfos * 2);
    if (!bigger.infos || !bigger.index)
    {
        releaseCache(&bigger, nullptr);
        return;
    }

    memcpy(bigger.infos, cache->infos, (size_t)cache->numInfos * sizeof(FileInfo));
    memcpy(bigger.index, cache->index, (size_t)cache->numIndex * sizeof(FileIndex));

    FileInfoCache old = *cache;
    cache->infos = bigger.infos;
    cache->maxInfos = bigger.maxInfos;
    cache->index = bigger.index;
    cache->maxIndex = bigger.maxIndex;
    releaseCache(&old, nullptr);
}

void Init()
{
    // The cache's constructor allocates both lists for a given number of files
    createCache = (Create_t)hook::get_pattern("53 55 56 57 8B 7C 24 14 8B F1 33 DB 33 C9 8B C7 BA 10 00 00 00 F7 E2");

    // Shutdown releases the cache's lists before freeing the cache itself
    releaseCache = (Release_t)FollowCall(hook::get_pattern("8B 0D ? ? ? ? 3B CF 89 3D ? ? ? ? 74 ? 56 8B F1 E8", 19));

    // The full-list check (mNumActiveFileInfos < mMaxFileInfos) before each file is added: grow instead
    overflowHook = safetyhook::create_mid(hook::get_pattern("8B 56 04 3B 56 08 7C ? 38 1D"), [](SafetyHookContext& regs)
    {
        FileInfoCache* cache = (FileInfoCache*)regs.esi;
        if (cache->numInfos >= cache->maxInfos)
            Grow(cache);
    });
}
