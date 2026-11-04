"""Checks the snippets and writes catalog.json, the one file fusionfix.io and FusionFixHub read.

    python tools/catalog.py            check everything, then write catalog.json
    python tools/catalog.py --check    check everything and that catalog.json is current (CI)
    python tools/catalog.py --compile  also compile each snippet with Ultimate ASI Loader's compiler (cxxcheck):
                                       CXXCHECK32 / CXXCHECK64 name the 32-bit and 64-bit cxxcheck.exe

Python 3.9 or later, nothing to install. Exit code 1 on any problem, each one printed.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "Fusion-Fix/FusionFixSnippets"
BRANCH = "main"
MAX_SNIPPET = 64 * 1024
NOT_GAMES = {"schema", "tools"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# The part of JSON Schema schema/snippets.schema.json uses
def validate(value, schema, where, problems):
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool}
    if kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            problems.append(f"{where}: must be a whole number")
            return
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{where}: must be at least {schema['minimum']}")
    elif kind:
        if not isinstance(value, types[kind]) or (kind != "boolean" and isinstance(value, bool)):
            problems.append(f"{where}: must be {'an' if kind in ('object', 'array') else 'a'} {kind}")
            return
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{where}: must be one of {', '.join(json.dumps(e) for e in schema['enum'])}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1 << 30):
            problems.append(f"{where}: length must be {schema.get('minLength', 0)} to {schema.get('maxLength', 'any')}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{where}: {json.dumps(value)} doesn't match {schema['pattern']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            problems.append(f"{where}: needs at least {schema['minItems']} entries")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            problems.append(f"{where}: has an entry twice")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{where}[{i}]", problems)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{where}: {key} is missing")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], f"{where}.{key}", problems)
            elif schema.get("additionalProperties") is False:
                problems.append(f"{where}: unknown field {key}")


def version(text):
    return tuple(int(x) for x in text.split("."))


def game_folders():
    for name in sorted(os.listdir(ROOT), key=str.lower):
        path = os.path.join(ROOT, name)
        if os.path.isdir(path) and not name.startswith(".") and name not in NOT_GAMES:
            yield name, path


def build(problems):
    schema = load_json(os.path.join(ROOT, "schema", "snippets.schema.json"))
    loader = load_json(os.path.join(ROOT, "loader.json"))
    names = {n.lower() for n in loader["names"]}
    catalog = {"format": 1, "repo": REPO, "loader": loader, "games": {}}
    ids = {}
    for folder, path in game_folders():
        index_path = os.path.join(path, "snippets.json")
        if not os.path.isfile(index_path):
            problems.append(f"{folder}: no snippets.json")
            continue
        try:
            index = load_json(index_path)
        except (ValueError, UnicodeDecodeError) as e:
            problems.append(f"{folder}/snippets.json: not JSON: {e}")
            continue
        before = len(problems)
        validate(index, schema, f"{folder}/snippets.json", problems)
        if len(problems) != before:
            continue
        game = index["game"]
        if folder.lower() != game["id"]:
            problems.append(f"{folder}/snippets.json: game.id must be the folder's name in lower case ({folder.lower()})")
        if game["id"] in catalog["games"]:
            problems.append(f"{folder}: game {game['id']} has two folders")
        if game["loader"].lower() not in names:
            problems.append(f"{folder}/snippets.json: game.loader {game['loader']} isn't a name Ultimate ASI Loader can have (loader.json names)")
        entry = {"folder": folder, "title": game["title"], "exe": game["exe"], "arch": game["arch"], "loader": game["loader"],
                 "exeFolder": game.get("exeFolder", "")}
        if "steamAppId" in game:
            entry["steamAppId"] = game["steamAppId"]
        entry["snippets"] = []
        listed = set()
        for s in index["snippets"]:
            where = f"{folder}/snippets.json {s['id']}"
            stem = s["file"][:-4]
            if s["id"] != f"{folder}.{stem}":
                problems.append(f"{where}: the id must be {folder}.{stem}")
            if s["id"].lower() in ids:
                problems.append(f"{where}: the id is used by {ids[s['id'].lower()]} too")
            ids[s["id"].lower()] = where
            if s["file"].lower() in listed:
                problems.append(f"{where}: {s['file']} is listed twice")
            listed.add(s["file"].lower())
            if version(s["loader"]) < version(loader["snippetsSince"]):
                problems.append(f"{where}: loader must be {loader['snippetsSince']} or later (the first release that runs snippets as they are now)")
            exe = s.get("exe", game["exe"])
            if any(e.lower() not in {g.lower() for g in game["exe"]} for e in exe):
                problems.append(f"{where}: exe lists a file that isn't in game.exe")
            file_path = os.path.join(path, s["file"])
            if not os.path.isfile(file_path):
                problems.append(f"{where}: {s['file']} isn't there")
                continue
            data = open(file_path, "rb").read()
            if len(data) > MAX_SNIPPET:
                problems.append(f"{where}: {s['file']} is larger than {MAX_SNIPPET // 1024} KB")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{where}: {s['file']} isn't UTF-8")
                continue
            # One text on every checkout, whatever git does with line ends
            text = text.lstrip("﻿").replace("\r\n", "\n")
            if "\0" in text:
                problems.append(f"{where}: {s['file']} has a NUL character")
            if not re.search(r"\bvoid\s+Init\s*\(\s*(void)?\s*\)", text):
                problems.append(f"{where}: {s['file']} has no void Init()")
            raw = text.encode("utf-8")
            target = "/".join(p for p in (game.get("exeFolder", ""), s["folder"], s["file"]) if p)
            entry["snippets"].append({
                "id": s["id"], "title": s["title"], "description": s["description"], "file": s["file"], "folder": s["folder"],
                "path": target, "exe": exe, "arch": s.get("arch", [game["arch"]]), "loader": s["loader"], "author": s["author"],
                **({"source": s["source"]} if "source" in s else {}), "default": s.get("default", False),
                "url": f"https://github.com/{REPO}/blob/{BRANCH}/{folder}/{s['file']}",
                "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "text": text,
            })
        for name in sorted(os.listdir(path)):
            if name.lower().endswith(".cxx") and name.lower() not in listed:
                problems.append(f"{folder}/{name}: not listed in snippets.json")
        catalog["games"][game["id"]] = entry
    return catalog


def compile_all(catalog, problems):
    tools = {"win32": os.environ.get("CXXCHECK32"), "x64": os.environ.get("CXXCHECK64")}
    for game in catalog["games"].values():
        for s in game["snippets"]:
            for arch in s["arch"]:
                tool = tools[arch]
                if not tool or not os.path.isfile(tool):
                    problems.append(f"{s['id']}: no {arch} cxxcheck.exe (CXXCHECK{'32' if arch == 'win32' else '64'})")
                    continue
                result = subprocess.run([tool, os.path.join(ROOT, game["folder"], s["file"])], capture_output=True, text=True)
                print(result.stdout.strip())
                if result.returncode:
                    problems.append(f"{s['id']}: doesn't compile for {arch}")


def main():
    problems = []
    catalog = build(problems)
    if "--compile" in sys.argv and not problems:
        compile_all(catalog, problems)
    text = json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    target = os.path.join(ROOT, "catalog.json")
    if not problems:
        if "--check" in sys.argv:
            current = open(target, "r", encoding="utf-8").read().replace("\r\n", "\n") if os.path.isfile(target) else ""
            if current != text:
                problems.append("catalog.json isn't current: run python tools/catalog.py and commit it")
        else:
            with open(target + ".tmp", "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(target + ".tmp", target)
    for p in problems:
        print(f"error: {p}")
    count = sum(len(g["snippets"]) for g in catalog["games"].values())
    print(f"{len(catalog['games'])} games, {count} snippets: {'failed' if problems else 'ok'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
