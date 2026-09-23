# Release checklist

This project is pre-alpha. **Do not publish an IPA as a complete or supported release until its corresponding source and dependencies have been assembled.** GitHub Releases should contain binaries; the git tree should contain the source, patches, build scripts and documentation.

## Files needed for the first source-matched release

1. Exact modified `blender-ios6-target` source snapshot, including the iOS GHOST/UIKit integration, Python/RNA fixes and UI changes.
2. The exact linker script (currently `blender-link-ios-python-v3.py`) and packager used for the IPA.
3. A description of the base Blender source revision and all source patches, including local changes not yet represented by standalone scripts.
4. Dependency manifest (versions, upstream URLs, license notices and build commands for CPython 3.3.x, GL4ES and other static libraries). Do not upload proprietary SDKs or privately licensed assets.
5. The device-tested IPA, its SHA-256 hash, the Mach-O UUID and the bundle ID.
6. Screenshots and a short known-issues section that reflects the tested build rather than promises of future features.

## Checks

- [ ] Confirm the source archive and packaged executable refer to the same changes.
- [ ] Run a fresh or documented clean build; retain the compiler/linker logs.
- [ ] Check IPA ZIP integrity and the expected `Payload/Blender3GS.app/Blender3GS` executable.
- [ ] Check architecture (`armv7`), iOS deployment target, bundle ID and version fields.
- [ ] Verify startup, viewport and Add menu on an actual iPhone 3GS.
- [ ] Test selection and navigation, including touch interaction with a popup.
- [ ] Test Properties: Render, Object, Modifiers and Material.
- [ ] Verify `Add Modifier` on the cube or mark it explicitly broken.
- [ ] Profile peak memory and record approximate performance before using optimization claims.
- [ ] Remove private device identifiers, user paths, account data, credentials, signatures and provisioning material from uploaded logs.
- [ ] Include corresponding GPL-licensed Blender source, notices and license text; review each third-party dependency's separate requirements.

## Suggested release naming

First release: `v0.1.0-alpha.1` — **Blender 3GS experimental preview**.

Release notes must clearly state the device, OS, architecture, what was observed working, what is incomplete, and how to install. Avoid naming the release `stable` while native Properties, rendering and project workflows are unverified.

## Asset naming

```text
Blender3GS-iPhone3GS-iOS6-armv7-v0.1.0-alpha.1.ipa
Blender3GS-source-v0.1.0-alpha.1.tar.gz
SHA256SUMS.txt
```

Do not put large build directories, downloaded SDKs, private iPhone logs or experimental IPA history into the main git repository. Use a distinct tag and GitHub Release assets for the matching binary and source snapshot.
