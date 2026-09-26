# UI37–UI44 development snapshot (25 September 2026)

This directory tracks the **native iPhone 3GS / iOS 6.1.6** Blender 2.64 experiments. These are sequential **development patches**, not a reproducible source release; a matching full modified source tree, complete dependency/link manifest and tested IPA have not yet been committed.

## Chronology

| UI | Focus | Evidence / limitations |
| --- | --- | --- |
| 37 | Deferred `bl_ui` / `bl_operators` registration, diagnostic CPU icon-buffer path | Device import improved but stage returned errors and complete UI was not preserved. Fixed build-script archive supersedes first packaging attempt. |
| 38 | More aggressive initial Python module subset | Device first frame still slow; deferred stages returned errors. |
| 39 Core | Trim unnecessary editors/operators for constrained 3D use | 119 panels after staged loading, versus 227 in earlier UI36 full-profile run. Intentional functional reduction. |
| 40 | **Native 3D frame before Python initialization** | Device logs show `native_frame_done` preceding `late_python_begin`; first Viewport roughly 3–4 s after launch, then Python work on the main thread. Fixed build-script archive supersedes the initial patch check. |
| 41 | Defer preview DB and experiment with temporary Bounding Box on first frame | Warm launches felt faster; first 3D draw still around one second; visual defects remained. |
| 42 | Safe diagnostic removing temporary Bounding Box | Prepared; no physical-device validation recorded. |
| 43 | Hide problematic camera/lamp viewport gizmos, try lazy 16×16 icon textures | **Tested screenshot**: large white triangle and camera rectangle disappear; white cross-editor lines and UI icon artifacts remain. Packaging-fix archive supersedes the initial package check. |
| 44 | Experimental GL-state/scissor isolation, simplified camera/lamp markers | **Prepared, not verified on the phone as of this snapshot.** |

The device screenshots are named by original capture time. `Blender3GS-20260925-111459.png` depicts the problematic large triangle/rectangle; `Blender3GS-20260925-113500.png` depicts UI43 after suppression, with remaining white lines/icon problems. Earlier 24 September screenshots show prior stages and are not necessarily UI41.

## Source and asset policy

- `bundles/` preserves the original downloadable patch-script ZIPs, including superseded versions for archaeology. The corresponding loose scripts are extracted into `scripts/<bundle-name>/`.
- `screenshots/` contains original device PNGs; preserve their bytes and original names. The SHA-256 manifest is in `SHA256SUMS`.
- Do **not** publish the raw device syslogs: they contain account-identifying information. Include only manually redacted excerpts if needed.
- Do **not** confuse these patch scripts with a complete source release. They depend on source markers, local build paths and a base IPA. Keep the GPL-compatible corresponding-source release checklist in `docs/RELEASE.md`.
- Do not publish unreviewed IPA binaries, signing files, private keys or provisioning artifacts.

## Updating these assets from the development Mac

Run the checked-in [synchronization script](../../scripts/sync-ui37-ui44-from-mac.sh) on the Mac holding the originals, from a terminal with git push access. It verifies all asset checksums and uploads **only explicit filenames**, not unrelated files from Downloads.

**Current status:** Documentation for the milestone is committed separately. The binary ZIP/PNG assets are available in this directory only once their synchronization commit is present.
