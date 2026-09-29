# Install the 2026-09-29 pre-alpha

Release: [pre-alpha-2026-09-29](https://github.com/arutiunio/blender-ios6/releases/tag/pre-alpha-2026-09-29)

The tested package is:

- `Blender3GS-python-ui-v43-visual-diagnostic.ipa`
- target: iPhone 3GS
- architecture: ARMv7
- minimum iOS: 6.0
- tested OS: iOS 6.1.6 on a jailbroken device
- bundle ID: `io.arutiunio.blender3gs.python`
- app version: `0.43.0` / bundle version `44`
- Mach-O UUID: `46B37BAC-2740-3BB0-943B-36F74E41E39A`
- IPA SHA-256: `76e6f783b06df5d67059db23a6500a8a7dabf73cf42f656eb2d38b4bf9f15362`

This is a jailbreak-only development build, not an App Store package.

## USB installation from macOS

A working paired-device setup with libimobiledevice is the simplest path used during development.

```sh
brew install libimobiledevice ideviceinstaller
idevice_id -l
ideviceinstaller install ~/Downloads/Blender3GS-python-ui-v43-visual-diagnostic.ipa
```

The device needs a compatible jailbreak/AppSync-style installation environment. If `ideviceinstaller` reports an installation/signature error, fix the device-side package installation setup first rather than changing the IPA.

Older development scripts refer to `/private/var/tmp/ios6-installer`. That helper is not guaranteed to exist on another phone and is not required when `ideviceinstaller` works.

## What to expect

UI43 is a pre-alpha diagnostic build. A real 3D viewport starts and embedded Python loads, but the interface is incomplete and some graphics are corrupted. The old Camera/Lamp helper path is suppressed because it produced large white geometry artifacts. White lines/icon corruption can still occur.

UI44 in the same release is **patch source only**. There is no device-tested UI44 IPA in this release.

## Verify the download

```sh
shasum -a 256 Blender3GS-python-ui-v43-visual-diagnostic.ipa
```

Expected:

```text
76e6f783b06df5d67059db23a6500a8a7dabf73cf42f656eb2d38b4bf9f15362
```

For source and development assets, use the release SHA-256 manifest.
