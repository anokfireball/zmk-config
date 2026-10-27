"""Narrow regression tests for LINK_* alias handling in format_keymap."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from format_keymap import (  # noqa: E402
    ORIGIN,
    PITCH,
    ROWS,
    KeymapFormatError,
    format_keymap,
    geometry,
)

LAYERS = ("default_layer", "mac_layer", "lower_layer", "raise_layer", "system_layer")


def make_keymap(tokens=None, aliases=()):
    """Five layers, 60 comma-separated one-binding groups, optional aliases."""
    tokens = list(tokens or ["&trans"] * 60)
    assert len(tokens) == 60
    definitions = "".join(f"#define {name} {value}\n" for name, value in aliases)
    bindings = ",\n".join(f"<{token}>" for token in tokens)
    layers = "".join(
        f"""        {name} {{
            display-name = "{name}";
            bindings =
{bindings};
        }};
"""
        for name in LAYERS
    )
    return f"""#include <dt-bindings/zmk/keys.h>
{definitions}
/ {{
    keymap {{
        compatible = "zmk,keymap";
{layers}    }};
}};
"""


class FormatterTests(unittest.TestCase):
    def test_seeds_eight_canonical_aliases_only_without_source_defines(self):
        output = format_keymap(make_keymap())
        self.assertEqual(output.count("#define LINK_"), 8)

    def test_extra_alias_is_accepted_and_used_directly(self):
        tokens = ["LINK_CTL"] + ["&trans"] * 59
        source = make_keymap(tokens, [("LINK_CTL", "&kp LCTRL")])
        output = format_keymap(source)
        self.assertEqual(output.count("#define LINK_"), 1)
        self.assertIn("#define LINK_CTL &kp LCTRL", output)
        self.assertIn("<LINK_CTL>", output)
        self.assertIn("LCTL", output)
        self.assertEqual(format_keymap(output), output)

    def test_lookup_comes_from_actual_source_definition(self):
        tokens = ["&kp KP_MULTIPLY"] + ["&trans"] * 59
        source = make_keymap(tokens, [("LINK_MEGA", "&kp KP_MULTIPLY")])
        output = format_keymap(source)
        self.assertEqual(output.count("#define LINK_"), 1)
        self.assertIn("<LINK_MEGA>", output)
        self.assertNotIn("<LINK_MULT>", output)
        self.assertEqual(format_keymap(output), output)

    def test_redefined_alias_does_not_map_unrelated_overlong_literal(self):
        tokens = ["&kp KP_MULTIPLY"] + ["&trans"] * 59
        source = make_keymap(tokens, [("LINK_MULT", "&kp LCTRL")])
        with self.assertRaises(KeymapFormatError):
            format_keymap(source)

    def test_duplicate_alias_rejected(self):
        source = make_keymap(
            aliases=[("LINK_CTL", "&kp LCTRL"), ("LINK_CTL", "&kp LCTRL")]
        )
        with self.assertRaisesRegex(KeymapFormatError, "duplicate"):
            format_keymap(source)

    def test_function_like_alias_rejected(self):
        source = make_keymap().replace(
            "#include <dt-bindings/zmk/keys.h>\n",
            "#include <dt-bindings/zmk/keys.h>\n#define LINK_CTL(x) &kp LCTRL\n",
            1,
        )
        with self.assertRaisesRegex(KeymapFormatError, "function-like"):
            format_keymap(source)

    def test_row3_has_seven_adjacent_cells_per_half(self):
        left, right = geometry(ROWS[3])[:7], geometry(ROWS[3])[7:]
        self.assertEqual([cell[0] for cell in left], [ORIGIN + i * PITCH for i in range(7)])
        self.assertEqual([cell[0] for cell in right], [ORIGIN + i * PITCH for i in range(10, 17)])
        for cells in (left, right):
            for previous, current in zip(cells, cells[1:]):
                self.assertEqual(previous[1], current[0])

    def test_thumb_row_has_five_adjacent_cells_per_half(self):
        left, right = geometry(ROWS[4])[:5], geometry(ROWS[4])[5:]
        self.assertEqual([cell[0] for cell in left], [ORIGIN + i * PITCH for i in range(2, 7)])
        self.assertEqual([cell[0] for cell in right], [ORIGIN + i * PITCH for i in range(10, 15)])
        for cells in (left, right):
            for previous, current in zip(cells, cells[1:]):
                self.assertEqual(previous[1], current[0])

    def test_art_has_no_phantom_cells_after_slot_snapping(self):
        output = format_keymap(make_keymap())
        start = output.index("        default_layer {")
        end = output.index("        };", start)
        art = [line for line in output[start:end].splitlines() if line.startswith("// ")]
        self.assertEqual(len(art), 5)
        expected_row3 = [ORIGIN + i * PITCH for i in range(0, 8)]
        expected_row3 += [ORIGIN + i * PITCH for i in range(10, 18)]
        expected_row4 = [ORIGIN + i * PITCH for i in range(2, 8)]
        expected_row4 += [ORIGIN + i * PITCH for i in range(10, 16)]
        for line, expected in ((art[3], expected_row3), (art[4], expected_row4)):
            self.assertEqual([i for i, char in enumerate(line) if char == "|"], expected)


if __name__ == "__main__":
    unittest.main()
