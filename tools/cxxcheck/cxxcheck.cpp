// cxxcheck: compiles .cxx snippets with Ultimate ASI Loader's own snippet compiler, without running them.
//
//   cxxcheck <file.cxx> [<file.cxx> ...]
//
// Prints each file's errors as "file(line,col): error: message" and exits with the number of files that failed.
// A 32-bit build checks snippets for 32-bit games, a 64-bit build for 64-bit games (the compiler targets the
// architecture of the process it runs in). Build: see the README's "Checking a snippet".
#include <cstdio>
#include <string>
#include <vector>
#include "cxxsnippets.hpp"

int main(int argc, char** argv)
{
    if (argc < 2)
    {
        std::fprintf(stderr, "usage: cxxcheck <file.cxx> [<file.cxx> ...]\n");
        return 1;
    }
    int failed = 0;
    for (int i = 1; i < argc; ++i)
    {
        std::vector<cxxsnippets::Diagnostic> errors;
        cxxsnippets::Options options;
        if (cxxsnippets::CheckFile(argv[i], options, errors))
        {
            std::printf("%s: ok (%s)\n", argv[i], sizeof(void*) == 8 ? "x64" : "win32");
            continue;
        }
        ++failed;
        if (errors.empty())
            std::printf("%s: error: not valid\n", argv[i]);
        for (auto& error : errors)
            std::printf("%s\n", error.ToString().c_str());
    }
    return failed;
}
