# Draft release notes — v0.1.0-alpha.1

> **DRAFT — NOT A PUBLISHED RELEASE.** Update the asset names, SHA-256 hash, source commit and device-test results after collecting the actual source and IPA.

## Blender 3GS: experimental native Blender 2.64 preview

A native ARMv7 Blender 2.64 port for a jailbroken iPhone 3GS running iOS 6.1.6. It includes a custom UIKit/GHOST window layer, OpenGL ES 2.0 compatibility rendering, embedded Python 3.3 and experimental trackpad-style touch controls.

### Observed working on physical hardware

- Startup to the native Blender interface and the default scene.
- 3D viewport interaction and native Add popup.
- More readable menu text following the UI rendering work.
- Expanded native Properties area in the mobile layout.

### Known issues

- Properties labels, icon tabs and settings panels are incomplete.
- Adding modifiers, render settings and material editing are not yet fully validated.
- Performance, complex scene support, file handling, rendering and long sessions are experimental.
- Requires jailbreak and a compatible iOS 6 SSH/installation setup; not an App Store build.

### Assets (to be supplied)

- Matching ARMv7 IPA
- Complete corresponding source archive or tagged source commit
- SHA256SUMS.txt

### Installation

Keep a USB `iproxy 2222:22` tunnel running and install the downloaded IPA using `scp -O` and `ios6-installer`. See [BUILD.md](BUILD.md) for the full command sequence.

### Source and credits

Based on Blender 2.64. Blender copyright belongs to the Blender Foundation and contributors. BlenderPocket is a separate historical project and is not bundled by implication. Consult the included licenses and corresponding-source notes before redistributing binaries.
