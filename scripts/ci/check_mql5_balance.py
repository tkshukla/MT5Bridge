#!/usr/bin/env python3
"""
Basic MQL5 sanity check: verifies brace/paren/bracket balance per file, ignoring
characters inside string literals ("...") and char literals ('.') and // comments,
since those can legitimately contain '{', '}', etc. (see JsonHelper.mqh's char-literal
comparisons like `c == '{'`). This is NOT a real compiler — MetaEditor isn't available
in Linux CI — it only catches gross structural errors like a missing closing brace.
"""

import sys


def strip_literals_and_comments(text: str) -> str:
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if c in ("'", '"'):
            quote = c
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\":
                    i += 1
                i += 1
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def check_file(path: str) -> bool:
    text = strip_literals_and_comments(open(path, encoding="utf-8").read())
    ok = True
    for open_c, close_c in [("{", "}"), ("(", ")"), ("[", "]")]:
        if text.count(open_c) != text.count(close_c):
            print(f"::error file={path}::unbalanced {open_c}{close_c} "
                  f"({text.count(open_c)} vs {text.count(close_c)})")
            ok = False
    if ok:
        print(f"OK: {path}")
    return ok


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not all(check_file(p) for p in paths):
        sys.exit(1)
