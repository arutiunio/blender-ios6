# Blender 3GS — Blender 2.64 for iOS 6

Experimental **native ARMv7 port of Blender 2.64** for the jailbroken **iPhone 3GS (iOS 6.1.6)**. This project aims to make the original Blender editor—not a remote desktop client or a scene viewer—run on the device.

> **Status: pre-alpha / work in progress.** The application runs on an iPhone 3GS, draws the 3D viewport and opens native Blender menus. The touch controls and mobile screen layout are being developed. The Properties editor is not yet fully usable. This repository is being assembled; do not assume that a reproducible full source tree or downloadable IPA is available until explicitly published.

## Hardware and software

- Target: iPhone 3GS, ARMv7, 480 × 320 landscape, iOS 6.1.6, jailbroken.
- Blender: 2.64 (legacy source tree).
- UI / window integration: custom iOS GHOST / UIKit implementation.
- Graphics: OpenGL compatibility layer over native OpenGL ES 2.0.
- Scripting: embedded CPython 3.3.x with Blender Python integration.
- Host build environment used during development: Apple Silicon Mac and Xcode 26.6, with an iOS 6-compatible SDK/toolchain setup.

## What works so far

- Native application startup and a functional 3D viewport.
- Blender's default scene, selection, navigation and several native menus.
- Experimental trackpad-style touch interaction.
- Corrected ARMv7 RNA parameter layout and embedded Python `atexit` registration.
- Updated font and icon rendering paths.
- A wider, native Properties area in the mobile screen layout.

## Known limitations

- The Properties editor still has missing labels, icons and/or panel content. Modifiers, materials and render settings are **not yet verified as usable**.
- Mobile UI layout, text rendering, touch input and performance remain experimental.
- Some graphics changes have caused startup crashes in older test builds. A successful package build does not imply successful on-device operation.
- Rendering, saving and loading complex projects, add-ons and long-running workloads have not been validated.
- This is not the modern Blender 5.x interface shown in desktop screenshots.

## Repository layout (planned)

| Path | Purpose |
| --- | --- |
| `patches/` | Reviewed changes against the exact upstream Blender source revision. |
| `ios/` | iOS GHOST/UIKit integration and supporting source. |
| `scripts/` | Build, link and IPA packaging scripts. |
| `docs/BUILD.md` | Build prerequisites and reproduction notes. |
| `docs/RELEASE.md` | Device testing, licensing and release checklist. |
| `docs/STATUS.md` | Verified progress and outstanding problems. |

The source and scripts will be populated from the actual development tree rather than reconstructed from screenshots or incomplete chat excerpts.

**Developer handoff:** [What to send for the source-matched release](docs/SEND-FILES.md). Archived experimental scripts are in [historical-patches](historical-patches/README.md).

## Installation

**Only install a release asset that explicitly identifies itself as an iPhone 3GS / iOS 6 ARMv7 build.** This is jailbreak-only software and is not an App Store app. The experimental Python application uses bundle identifier `io.arutiunio.blender3gs.python`, separate from the earlier Touch v2 test app.

See [Build and installation notes](docs/BUILD.md). Release assets, checksums and a matching source snapshot will be added together when available.

## Upstream and licensing

Blender is developed by the Blender Foundation and contributors. BlenderPocket, by Salvatore Russo, is a separate historical Windows Mobile port; this repository is **not** an official Blender or BlenderPocket release.

This project contains modifications to GPL-licensed Blender code. Distribution of binaries must be accompanied by the corresponding source code and applicable copyright notices/licenses. Third-party dependencies (including Python and the OpenGL compatibility layer) retain their respective licenses. See [release checklist](docs/RELEASE.md).

## Contributing

Reproducible crash reports, device screenshots, fixes for the legacy UI, ARMv7 build improvements and documented profiling results are welcome. Please include the build identifier, iOS version and steps to reproduce. Do not upload private device logs, credentials or personal data.
