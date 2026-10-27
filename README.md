# ZMK config for the CannonKeys Link (wireless)

Keymap and build configuration for the Link, built against
[`zmk-cannonkeys-keyboards`](https://github.com/cannonkeys/zmk-cannonkeys-keyboards).

## How it works

- **Firmware source**: `config/west.yml` pins CannonKeys' board module and upstream ZMK
  (`v0.3-branch`, Zephyr 3.5) to exact commits.
- **Builds**: GitHub Actions builds `build.yaml` on every push to `main` and on every pull request inside the
  `zmk-build-arm:3.5-branch` container (the `stable` image is Zephyr 4.x and cannot build these boards).
  Pushes to `main` publish `link_left.uf2`, `link_right.uf2` and `checksums.txt` as a GitHub release,
  unless the firmware checksums match the latest release.
- **Updates**: Renovate tracks the GitHub Actions, the build image digest, and both `west.yml` pins.
- **Keymap**: `config/link.keymap` overrides the board's default keymap: a Windows/Linux base
  layer, a macOS overlay, and the usual lower/raise/tri-layer setup.

## Typing on macOS vs Windows

ZMK has no equivalent of QMK's `OS_DETECTION_ENABLE`: it never asks the host what it is (there is
nothing to ask over BLE anyway), so the modifier layout is picked with a key instead of detected.

| Mode | Layout |
| --- | --- |
| `WIN` (power-on default) | Ctrl innermost, GUI outermost: `LGUI LALT LCTRL` … `RCTRL RALT RGUI` |
| `MAC` | Cmd innermost, Ctrl outermost: `LCTRL LALT LGUI` … `MEGA RALT RCTRL` |

That is the same Cmd/Ctrl placement as the home-row mods on the other boards. In `MAC` mode the
innermost right modifier becomes **MEGA** — tap = right Cmd, hold = Ctrl+Alt+Cmd — the right-thumb
role from the ergo board's keymap. Alt/Option, Shift, media keys, encoders and every other layer
are shared; the mode is an overlay sitting directly above the base layer, so SYMBOL/NAV/SYSTEM
keep working unchanged in both modes.

To switch, hold RAISE and press the top-left corner for macOS or the top-right corner for Windows
(the same corners that carry the reset keys on the LOWER+RAISE layer). Every layer has a
`display-name` describing its use — `WIN`, `MAC`, `SYMBOL`, `NAV`, `SYSTEM` — so the nice!view
(which shows the highest active layer) and Studio name the current state instead of printing a
layer index.

Layer state lives in RAM: a power cycle or a reset drops back to `WIN`.

Holding LOWER+RAISE also exposes a lock key beside each reset corner: `M:LOCK` third from the left
edge locks macOS (Ctrl+Cmd+Q) and `W:LOCK` third from the right edge locks Windows (Win+L) — the
same sides as the NAV corners that pick the OS mode. Reset and bootloader act on the half whose key
you press.

> **Upgrading an existing flash:** the overlay was inserted at layer index 1, so lower/raise/system
> are now layers 2/3/4. A keymap saved from Studio against the older build is keyed by layer index
> and must be discarded with "Restore Stock Keymap" before these layers behave as written.

## Resetting / entering the bootloader

The central (left) half owns the keymap: it decodes every key on the full keyboard, including the
right half's keys. Hold LOWER and RAISE together (the SYSTEM layer), then press:

| Key on the full keyboard | Effect |
| --- | --- |
| top-left grave (`` ` ``) | left half into bootloader |
| 2nd from top-left (`1`) | left half soft reset |
| 2nd from top-right (`0`) | right half soft reset |
| top-right minus (`-`) | right half into bootloader |

The grave key boots **only the left** half and the minus key boots **only the right** half — the
chord plus top-left does not put the right half into its bootloader. These bindings live in the
central half's compiled keymap, so they only work once that half is running this firmware. To
migrate from CannonKeys' stock firmware, or whenever the stock keymap has not been read, do not
guess at its chords: double-tap the physical reset button on each half in turn to put that half in
its bootloader. That works regardless of the flashed keymap and is the reliable fallback if a
chord does nothing or a half is unresponsive.

## Flashing

Put a half in bootloader mode, then copy its `.uf2` to the drive that shows up: `link_left.uf2` for
the left (central) half and `link_right.uf2` for the right half. Keymap-only changes only need
`link_left.uf2`, because the central half owns the keymap.

> **ZMK Studio caveat:** the left half is built with Studio enabled. Keymaps saved from Studio persist
> in flash and override the keymap compiled from this repo. Use "Restore Stock Keymap" in Studio
> after flashing if the keymap does not change.

## Build locally

```sh
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -w /w \
  zmkfirmware/zmk-build-arm:3.5-branch bash -c '
    west init -l config && west update --fetch-opt=--filter=tree:0 && west zephyr-export &&
    west build -s zmk/app -d build/left -b link_left -S studio-rpc-usb-uart -- \
      -DZMK_CONFIG=/w/config -DSHIELD=nice_view -DCONFIG_ZMK_STUDIO=y'
```
