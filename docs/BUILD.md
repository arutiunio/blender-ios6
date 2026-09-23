# Building and installing Blender 3GS

> This is a **development-environment record**, not yet a clean-room build guide. The current project depends on a modified Blender 2.64 source tree and local third-party libraries that still need to be inventoried and published or linked. Do not claim reproducibility until the source snapshot, dependency versions and build scripts have been verified together.

## Target

- iPhone 3GS, ARMv7, iOS 6.1.6, jailbroken.
- Landscape framebuffer: 480 × 320.
- Experimental app bundle ID: `io.arutiunio.blender3gs.python`.

## Development machine

The existing build was produced on an Apple Silicon Mac with Xcode 26.6, an iOS-compatible toolchain/SDK configuration, CMake/Ninja, Python 3 and iOS device tools such as `iproxy`, `scp` and `idevicesyslog`.

The working tree used these local paths:

```text
~/Downloads/blender-ios6-target/         modified Blender source
~/Downloads/blender-ios6-build-python/   experimental ARMv7 Ninja build
~/Downloads/blender-ios6-python/         Python source, intermediate objects and packagers
~/Downloads/ios-deps/                    local third-party dependencies
~/Downloads/blender-link-ios-python-v3.py
~/Downloads/Blender3GS-python-armv7
```

These are **historical local paths**, not repository layout requirements. They must be made configurable in the final build scripts.

## Current local rebuild procedure

For an existing machine with the same **already-prepared** build tree:

```sh
export DEVELOPER_DIR=/Applications/Xcode-26.6.app/Contents/Developer
export IOS_SDKROOT="$(xcrun --sdk iphoneos --show-sdk-path)"

ninja -C ~/Downloads/blender-ios6-build-python -j4 bf_windowmanager
python3 ~/Downloads/blender-link-ios-python-v3.py
```

For a full rebuild, use the exact CMake/Ninja configuration and dependency manifest from the forthcoming source snapshot. The two commands above alone are **not** sufficient to build from a fresh checkout.

When packaging, use the latest `Blender3GS-package-ui-vNN.py` script for the exact source revision being tested. Do not mix a new binary with an older package script without verifying the embedded resources, executable UUID and bundle ID.

## Install an existing experimental IPA

The phone must already have a compatible SSH server and `ios6-installer`. Keep `iproxy 2222:22` running in another terminal (as in the development setup).

Replace the example file name with the actual release asset:

```sh
IPA="$HOME/Downloads/Blender3GS-python-ui-v16-properties.ipa"
test -f "$IPA" || { echo "Missing IPA: $IPA"; exit 1; }

scp -O \
  -o HostKeyAlgorithms=+ssh-rsa \
  -o PubkeyAcceptedAlgorithms=+ssh-rsa \
  -P 2222 "$IPA" root@127.0.0.1:/private/var/tmp/

ssh \
  -o HostKeyAlgorithms=+ssh-rsa \
  -o PubkeyAcceptedAlgorithms=+ssh-rsa \
  -p 2222 root@127.0.0.1 \
  "/private/var/tmp/ios6-installer install /private/var/tmp/$(basename "$IPA")"
```

Open **Blender Py** on the phone. The SSH options are a legacy compatibility workaround for the iOS 6 SSH server; use a USB tunnel and trusted local connection.

## Device logs and screenshots

If `idevicesyslog` is already running, use that terminal to filter `Blender3GS` messages. Do not start a second redundant logger.

For a screenshot, use Home + Power on the phone and transfer the newest screenshot over the existing SSH tunnel. The development helper `Blender3GS-shot.sh` should be included in the source snapshot.

## Before publishing binaries

Record exact compiler and linker commands, source revision, CMake cache values, versions/licenses of GL4ES and other dependencies, SHA-256 checksums of the IPA, and the app's Mach-O UUID. Publish the complete corresponding GPL-covered source with the release.
