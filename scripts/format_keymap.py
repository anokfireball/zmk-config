#!/usr/bin/env python3
"""Regenerate art/binding cells in config/link.keymap.

Fixed 14-column pitch, 13-column interior, first art pipe at column 3; x from
link-layouts.dtsi is snapped to the nearest whole key unit before scaling, so
fractional 0.05-0.2u gaps cannot become phantom one-column cells.  The y
stagger is flattened to five rows.  One centered <binding> per key, commas at
right-pipe columns, final ';', visible text <= 11 chars.  On a file with no
LINK_* definitions the eight canonical aliases are seeded; otherwise the
file's own object-like definitions are authoritative.

    python3 scripts/format_keymap.py [path]
    python3 scripts/format_keymap.py --check [path]   # 1 on drift, no write
"""
import argparse
import re
import sys
from collections import namedtuple
from pathlib import Path

PITCH, INTERIOR, ORIGIN = 14, 13, 3
MAX_TEXT, TOTAL = 11, 60
ROWS = (
    (0, 100, 200, 300, 400, 500, 1100, 1200, 1300, 1400, 1500, 1600),
    (0, 100, 200, 300, 400, 500, 1100, 1200, 1300, 1400, 1500, 1600),
    (0, 100, 200, 300, 400, 500, 1100, 1200, 1300, 1400, 1500, 1600),
    (0, 100, 200, 300, 400, 500, 620, 980, 1100, 1200, 1300, 1400, 1500, 1600),
    (200, 300, 400, 515, 625, 982, 1095, 1200, 1300, 1400),
)
XS = tuple(x for row in ROWS for x in row)
LAYER_NAMES = ("default_layer", "mac_layer", "lower_layer", "raise_layer", "system_layer")
ARITY = {"kp": 1, "mo": 1, "to": 1, "bt": 2, "mega": 2, "trans": 0,
         "bootloader": 0, "sys_reset": 0, "studio_unlock": 0,
         "lock_mac": 0, "lock_win": 0}
BT_ONE = frozenset(("BT_CLR", "BT_NXT", "BT_PRV", "BT_CLR_ALL", "BT_DISC"))
BT_TWO = frozenset(("BT_SEL",))
ALIASES = (("LINK_MEGA", "&mega LC(LA(LGUI)) RGUI"), ("LINK_STUDIO", "&studio_unlock"),
           ("LINK_MULT", "&kp KP_MULTIPLY"), ("LINK_BT1", "&bt BT_SEL 0"),
           ("LINK_BT2", "&bt BT_SEL 1"), ("LINK_BT3", "&bt BT_SEL 2"),
           ("LINK_BT4", "&bt BT_SEL 3"), ("LINK_BT5", "&bt BT_SEL 4"))
KP = {
    "GRAVE": "`", "MINUS": "-", "ESC": "ESC", "BSPC": "BKSPC", "TAB": "TAB",
    "SEMI": ";", "APOS": "'", "LSHFT": "SHIFT", "RSHFT": "SHIFT",
    "C_MUTE": "MUTE", "C_PP": "PLAY", "COMMA": ",", "DOT": ".", "FSLH": "/",
    "LGUI": "LGUI", "LALT": "ALT", "LCTRL": "LCTL", "RET": "ENTER",
    "SPACE": "SPACE", "RCTRL": "RCTL", "RALT": "RALT", "RGUI": "RGUI",
    "EXCL": "!", "AT": "@", "HASH": "#", "DLLR": "$", "PRCNT": "%",
    "CARET": "^", "AMPS": "&", "KP_MULTIPLY": "*", "LPAR": "(", "RPAR": ")",
    "PIPE": "|", "EQUAL": "=", "PLUS": "+", "LBRC": "{", "RBRC": "}",
    "LBKT": "[", "RBKT": "]", "COLON": ":", "BSLH": "\\",
    "PGUP": "PGUP", "PGDN": "PGDN", "HOME": "HOME", "END": "END",
    "INS": "INS", "DEL": "DEL", "UP": "^", "DOWN": "v", "LEFT": "<-",
    "RIGHT": "->", "CAPS": "CAPS", "C_PREV": "PREV", "C_NEXT": "NEXT",
    "PSCRN": "PSCR",
}
Binding = namedtuple("Binding", "alias expr behavior params")


class KeymapFormatError(ValueError):
    pass


def fail(message):
    raise KeymapFormatError(message)


def norm(text):
    return " ".join(text.split())


def groups(value):
    """Return the text inside each <...> group, rejecting stray text."""
    result, index = [], 0
    while index < len(value):
        while index < len(value) and value[index].isspace():
            index += 1
        if index >= len(value):
            break
        if value[index] == ",":
            index += 1
            continue
        if value[index] != "<":
            fail(f"expected '<' before binding group, found {value[index]!r}")
        end = value.find(">", index + 1)
        if end < 0 or "<" in value[index + 1:end]:
            fail("malformed <...> binding group")
        result.append(value[index + 1:end])
        index = end + 1
    if not result:
        fail("bindings property has no <...> groups")
    return result


def split_tokens(text):
    """Split on whitespace and commas at parenthesis depth zero."""
    result, buffer, depth = [], [], 0
    for character in text:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                fail("unbalanced ')' in bindings")
        if depth == 0 and (character.isspace() or character == ","):
            if buffer:
                result.append("".join(buffer))
                buffer = []
        else:
            buffer.append(character)
    if depth:
        fail("unbalanced '(' in bindings")
    if buffer:
        result.append("".join(buffer))
    return result


def parse_cells(value, aliases):
    cells = []
    for group in groups(value):
        tokens = split_tokens(group)
        if not tokens:
            fail("empty <...> binding group")
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in aliases:
                alias = aliases[token]
                cells.append(Binding(token, alias.expr, alias.behavior, alias.params))
                index += 1
                continue
            if not token.startswith("&"):
                fail(f"unknown binding token {token!r}")
            behavior = token[1:]
            if behavior not in ARITY:
                fail(f"unsupported behaviour &{behavior}")
            if behavior == "bt":
                if index + 1 >= len(tokens) or tokens[index + 1] not in BT_ONE | BT_TWO:
                    fail("expected BT_SEL or BT_CLR after &bt")
                count = 1 if tokens[index + 1] in BT_ONE else 2
            else:
                count = ARITY[behavior]
            params = tokens[index + 1:index + 1 + count]
            if len(params) != count or any(p.startswith("&") or p in aliases for p in params):
                fail(f"&{behavior} expects {count} parameter(s)")
            expr = "&" + behavior + ((" " + " ".join(params)) if params else "")
            cells.append(Binding(None, expr, behavior, tuple(params)))
            index += 1 + count
    return cells


def read_aliases(source):
    lines = [line for line in source.splitlines() if line.lstrip().startswith("#define LINK_")]
    if not lines:
        return {}, False, {norm(value): name for name, value in ALIASES}
    found, order = {}, []
    for line in lines:
        if re.match(r"\s*#define\s+LINK_[A-Za-z0-9_]+\(.*", line):
            fail(f"function-like alias definition is not supported: {line!r}")
        match = re.match(r"\s*#define\s+(LINK_[A-Za-z0-9_]+)\s+(.+?)\s*$", line)
        if match is None:
            fail(f"malformed alias definition: {line!r}")
        name, value = match.group(1), norm(match.group(2))
        if name in found:
            fail(f"duplicate alias definition for {name}")
        if len(name) > MAX_TEXT:
            fail(f"alias {name} is too long for a fixed {INTERIOR}-column cell")
        parsed = parse_cells("<" + value + ">", {})
        if len(parsed) != 1:
            fail(f"alias {name} must expand to one binding")
        found[name] = parsed[0]
        order.append(name)
    by_expr = {}
    for name in order:
        expression = found[name].expr
        if len(expression) > MAX_TEXT and expression not in by_expr:
            by_expr[expression] = name
    return found, True, by_expr


def label(cell, x):
    behavior, params = cell.behavior, cell.params
    if behavior == "trans":
        return ""
    if behavior == "kp":
        code = params[0]
        if code in KP:
            return KP[code]
        if len(code) == 1 and "A" <= code <= "Z":
            return code
        if re.fullmatch(r"N[0-9]", code):
            return code[1]
        if re.fullmatch(r"F(?:[1-9]|1[0-2])", code):
            return code
        fail(f"no art label for keycode {code!r}")
    if behavior == "mo" and params[0] in ("2", "3"):
        return "LOWER" if params[0] == "2" else "RAISE"
    if behavior == "to" and params[0] in ("0", "1"):
        return "WIN" if params[0] == "0" else "MAC"
    if behavior == "bt":
        if params[0] == "BT_SEL" and len(params) == 2 and params[1] in ("0", "1", "2", "3", "4"):
            return "BT" + str(int(params[1]) + 1)
        if params == ("BT_CLR",):
            return "BTCLR"
        fail(f"no art label for &bt {' '.join(params)}")
    if behavior == "mega" and params == ("LC(LA(LGUI))", "RGUI"):
        return "MEGA"
    if behavior == "studio_unlock":
        return "ST.ULOCK"
    if behavior in ("bootloader", "sys_reset"):
        return ("L" if x < 800 else "R") + (":BOOT" if behavior == "bootloader" else ":RST")
    if behavior == "lock_mac":
        return "M:LOCK"
    if behavior == "lock_win":
        return "W:LOCK"
    fail(f"no art label for {cell.expr!r}")


def center(left, text):
    return left + 1 + (INTERIOR - len(text)) // 2


def geometry(row):
    # Snap centi-u x to the nearest whole 1u slot before applying the pitch.
    # This keeps adjacent keys adjacent (no phantom "| |" cells from tiny gaps).
    slots = [(x + 50) // 100 for x in row]
    return [(ORIGIN + slot * PITCH, ORIGIN + slot * PITCH + PITCH) for slot in slots]


def render_art(labels):
    lines, index = [], 0
    for row in ROWS:
        cells = geometry(row)
        canvas = [" "] * (cells[-1][1] + 1)
        canvas[0:3] = "// "
        for (left, right), text in zip(cells, labels[index:index + len(row)]):
            if len(text) > INTERIOR:
                fail(f"label {text!r} is too wide")
            canvas[left] = canvas[right] = "|"
            if text:
                canvas[center(left, text):center(left, text) + len(text)] = text
        lines.append("".join(canvas).rstrip())
        index += len(row)
    return lines


def token_for(cell, where, alias_by_expr):
    name = cell.alias or alias_by_expr.get(cell.expr)
    if name is None:
        if len(cell.expr) > MAX_TEXT:
            fail(f"{where}: {cell.expr!r} is too long; add a local LINK_* alias")
        name = cell.expr
    token = "<" + name + ">"
    if len(token) > INTERIOR:
        fail(f"{where}: binding token {token!r} is too wide")
    return token


def render_bindings(cells, alias_by_expr):
    lines, index = [], 0
    for row in ROWS:
        cells_in_row = geometry(row)
        canvas = [" "] * (cells_in_row[-1][1] + 1)
        for offset, (left, right) in enumerate(cells_in_row):
            number = index + offset
            token = token_for(cells[number], f"binding {number + 1}", alias_by_expr)
            start = center(left, token)
            canvas[start:start + len(token)] = token
            canvas[right] = ";" if number == TOTAL - 1 else ","
        lines.append("".join(canvas).rstrip())
        index += len(row)
    return lines


KEYMAP_RE = re.compile(r"(?ms)^    keymap \{\n(.*?)^    \};")
LAYER_RE = re.compile(r"(?ms)^        (\w+) \{\n(.*?)^        \};")
DISPLAY_RE = re.compile(r'display-name\s*=\s*"[^"]*"\s*;')
BIND_RE = re.compile(r"(?ms)^( +)bindings\s*=\s*(<.*?);")


def format_keymap(source):
    """Return source with regenerated art/bindings; pure and fail-closed."""
    if not isinstance(source, str):
        raise TypeError("format_keymap() expects a string")
    aliases, aliases_present, alias_by_expr = read_aliases(source)
    keymaps = list(KEYMAP_RE.finditer(source))
    if len(keymaps) != 1:
        fail("expected exactly one indented keymap { ... } block")
    keymap_start = keymaps[0].start(1)
    layers = list(LAYER_RE.finditer(keymaps[0].group(1)))
    if tuple(match.group(1) for match in layers) != LAYER_NAMES:
        fail("expected the five known layer nodes in order")
    parsed = []
    for match in layers:
        body = match.group(2)
        code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("//"))
        if "{" in code or "}" in code:
            fail(f"layer {match.group(1)} contains unsupported nested braces")
        display = list(DISPLAY_RE.finditer(body))
        binding = list(BIND_RE.finditer(body))
        if len(display) != 1 or len(binding) != 1:
            fail(f"layer {match.group(1)} needs one display-name and one bindings property")
        display, binding = display[0], binding[0]
        if display.end() > binding.start():
            fail(f"layer {match.group(1)} has bindings before display-name")
        for line in body[display.end():binding.start()].splitlines():
            if line.strip() and not line.strip().startswith("//"):
                fail(f"layer {match.group(1)} has unsupported content before bindings")
        cells = parse_cells(binding.group(2), aliases)
        if len(cells) != TOTAL:
            fail(f"layer {match.group(1)} has {len(cells)} bindings, expected {TOTAL}")
        parsed.append((keymap_start + match.start(2), keymap_start + match.end(2),
                       body, display, binding, cells))
    default_cells = parsed[0][5]
    replacements = []
    for layer_number, (start, end, body, display, binding, cells) in enumerate(parsed):
        labels = ["" if layer_number and cell.expr == default_cells[index].expr else label(cell, x)
                  for index, (cell, x) in enumerate(zip(cells, XS))]
        new_body = (body[:display.end()] + "\n" + "\n".join(render_art(labels)) + "\n"
                    + binding.group(1) + "bindings =\n" + "\n".join(render_bindings(cells, alias_by_expr))
                    + body[binding.end():])
        replacements.append((start, end, new_body))
    result = source
    for start, end, new_body in reversed(replacements):
        result = result[:start] + new_body + result[end:]
    if not aliases_present:
        includes = list(re.finditer(r"(?m)^#include[^\n]*\n", result))
        if not includes:
            fail("cannot place LINK_* aliases: no #include line")
        block = "\n" + "\n".join(f"#define {name} {value}" for name, value in ALIASES) + "\n"
        result = result[:includes[-1].end()] + block + result[includes[-1].end():]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Regenerate Link keymap art and binding cells.")
    parser.add_argument("path", nargs="?",
                        default=str(Path(__file__).resolve().parent.parent / "config/link.keymap"))
    parser.add_argument("--check", action="store_true",
                        help="do not write; exit 1 if formatting would change the file")
    args = parser.parse_args(argv)
    path = Path(args.path)
    try:
        source = path.read_text(encoding="utf-8")
        formatted = format_keymap(source)
    except (OSError, KeymapFormatError) as error:
        print(f"format_keymap: {error}", file=sys.stderr)
        return 2
    if args.check:
        if formatted != source:
            print(f"{path}: needs formatting", file=sys.stderr)
            return 1
        return 0
    if formatted != source:
        path.write_text(formatted, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
