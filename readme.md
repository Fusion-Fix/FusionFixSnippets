# FusionFixSnippets

Small game patches written as plain C++ `.cxx` files. [Ultimate ASI Loader](https://github.com/ThirteenAG/Ultimate-ASI-Loader)
(10.0.1 or newer) compiles them when the game starts: no Visual Studio, no build step. Players get them from the
game's page on [fusionfix.io](https://fusionfix.io) (tick the snippets you want, download one zip with the loader)
or from FusionFixHub.

## Using a snippet by hand

1. Put Ultimate ASI Loader into the game's folder under the name the game needs (the game's `snippets.json`,
   `game.loader`, e.g. `winmm.dll` for Alien: Isolation).
2. Put the `.cxx` file into the folder its entry names (usually `scripts\` next to the game's exe).
3. Start the game. A snippet that doesn't compile shows its file and line in a message, and the game still starts.

## Layout

```
<Game>/                       one folder per game; its name in lower case is the game's id on fusionfix.io
  snippets.json               the game and its snippets (format below)
  <Name>.cxx                  one file per snippet
loader.json                   where Ultimate ASI Loader comes from, the names it can have
schema/snippets.schema.json   the format of snippets.json (editors use it for completion and checks)
tools/catalog.py              checks everything and writes catalog.json
tools/cxxcheck/cxxcheck.cpp   compiles snippets with the loader's own compiler (see "Checking a snippet")
catalog.json                  generated: every game and snippet in one file, read by fusionfix.io and FusionFixHub
```

## snippets.json

```json
{
  "$schema": "../schema/snippets.schema.json",
  "game": {
    "id": "alienisolation",
    "title": "Alien: Isolation",
    "exe": ["AI.exe"],
    "arch": "win32",
    "loader": "winmm.dll",
    "steamAppId": 214490
  },
  "snippets": [
    {
      "id": "AlienIsolation.SkipSaveConfirmationDialog",
      "file": "SkipSaveConfirmationDialog.cxx",
      "title": "Skip save confirmation",
      "description": "Saves the game without asking for confirmation first.",
      "folder": "scripts",
      "loader": "10.0.1",
      "author": "ThirteenAG",
      "source": "https://github.com/ThirteenAG/AlienIsolation.SkipSaveConfirmationDialog",
      "default": true
    }
  ]
}
```

`game`:

| Field | |
|---|---|
| `id` | The game's id on fusionfix.io (`/games/<id>/`): the folder's name in lower case. A game that already has a page there uses that page's id, and its snippets show on that page. |
| `title` | The game's name. |
| `exe` | File names of the game's exe. FusionFixHub offers the snippets in a game folder with one of them. |
| `arch` | `win32` or `x64`: the exe's architecture, which decides the loader's build. |
| `loader` | The name the loader gets in this game's folder (one of `loader.json` `names`). |
| `exeFolder` | Optional: the exe's folder relative to the install folder when it is below it (`Gameface/Binaries/Win64`). The loader and the snippets go there. |
| `steamAppId` | Optional: the Steam app id. |

Each snippet:

| Field | |
|---|---|
| `id` | `<Folder>.<file name without .cxx>`. Never give a removed snippet's id to another one: share links and installs refer to it. |
| `file` | The `.cxx` file in this folder. |
| `title` | A short name: the label of its checkbox. |
| `description` | One plain sentence: what changes in the game. |
| `folder` | `scripts` (the usual), `plugins`, or `""` for the exe's folder itself. |
| `exe`, `arch` | Optional: only these exes or architectures, when not every one of the game's. |
| `loader` | The oldest Ultimate ASI Loader version it works with (10.0.1 or later). |
| `author` | Who made it. |
| `source` | Optional: where it comes from (a plugin's repository, a forum post). |
| `default` | Optional: ticked when the game's page opens. |

## Writing a snippet

Start the file with a comment that says what it does, which game and exe it is for, which versions it was made for
and what happens on others, and where it goes. Then the code:

```cpp
#include <injector/injector.hpp>
#include <Hooking.Patterns.h>

void Init()
{
    injector::WriteMemory<uint8_t>(hook::get_pattern("74 10 53 53 6A 1B"), 0xEB, true);
}
```

- `Init()` runs once the snippet is compiled; `Shutdown()` when it is unloaded (hot reload). Stop threads you started
  in `Shutdown()`.
- Find code by byte pattern (`Hooking.Patterns.h`), never by fixed address, so other builds of the game work or the
  snippet does nothing.
- Available: `injector/injector.hpp`, `Hooking.Patterns.h`, `safetyhook.hpp`, a small `<windows.h>`, `<cstdint>`,
  `<cstdio>`, `<cstring>`, and any function a loaded DLL exports (declared `extern "C"` inside
  `#ifdef __CXXSNIPPETS__`). No STL, templates, virtual functions or exceptions. The full list:
  [the snippet compiler's README](https://github.com/ThirteenAG/Ultimate-ASI-Loader/blob/master/source/loader/cxx/cxxsnippets/README.md);
  one example per common task: [examples/snippets](https://github.com/ThirteenAG/Ultimate-ASI-Loader/tree/master/examples/snippets).
- The same file builds as an `.asi` with Visual Studio for debugging (see the end of
  `AlienIsolation/SkipSaveConfirmationDialog.cxx`).

### Trying it in the game

Put `global.ini` next to the loader with

```ini
[GlobalSets]
CxxHotReload=1
```

and keep the game running while you edit: each save is compiled first; with errors they are shown and the running
version stays, otherwise the old version is unloaded (its patches undone) and the new one starts. Crashes in a
snippet are written to `<loader name>.log` with the file and line.

## Adding a snippet

1. A new game: a folder named like the game's id on fusionfix.io (look at the page's address; a game without a page
   gets one), with `snippets.json`.
2. The `.cxx` file and its entry in `snippets.json`.
3. `python tools/catalog.py`: checks the folder and writes `catalog.json`. Commit both.
4. fusionfix.io and FusionFixHub pick it up with their next update from this repository.

## Checking a snippet

`python tools/catalog.py --check` checks the metadata and that `catalog.json` is current; the CI workflow
(`.github/workflows/check.yml`) also compiles every snippet with the loader's own compiler for its architecture.

Locally, with Visual Studio 2026 and an Ultimate ASI Loader checkout built once (`premake5 vs2026`, then the
`cxxsnippets` project, Release, Win32 and x64), in a Developer Command Prompt for each architecture:

```
cl /nologo /std:c++latest /EHsc /O2 /MT /utf-8 /I <UAL>\source\loader\cxx\cxxsnippets tools\cxxcheck\cxxcheck.cpp /Fe:cxxcheck32.exe /link /LIBPATH:<UAL>\build\lib\Win32\Release cxxsnippets.lib psapi.lib user32.lib
set CXXCHECK32=%CD%\cxxcheck32.exe
python tools\catalog.py --compile
```

(the same with `x64` paths and `CXXCHECK64` for 64-bit games).
