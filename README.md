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
- **Keymap**: `config/link.keymap` overrides the board's default keymap.

## Resetting / entering the bootloader

Hold LOWER and RAISE together, then press:

| Key (system layer) | Effect |
| --- | --- |
| top-left | left half into bootloader |
| 2nd from top-left | left half soft reset |
| top-right | right half into bootloader |
| 2nd from top-right | right half soft reset |

Reset behaviors act on the half that owns the pressed key. The right half only reacts while it is
connected to the left (central) half. If a half is unresponsive, double-tap its reset button.

## Flashing

Put a half in bootloader mode, then copy the `.uf2` to the drive that shows up. Keymap-only changes
only need `link_left.uf2`.

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
