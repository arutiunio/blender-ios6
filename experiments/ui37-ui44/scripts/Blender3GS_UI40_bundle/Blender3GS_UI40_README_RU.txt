Blender3GS UI40: NATIVE FIRST FRAME (experimental, may crash)

Preconditions:
- UI37 FIXED/ UI39 Core was built in existing ~/Downloads project.
- ~/Downloads/Blender3GS-python-ui-v39-3d-core.ipa exists (CFBundleVersion 39).
- UI37 native wm.c, UI30 wm_init_exit.c and UI29 wm_draw.c baseline with UI21 retained backing are present.
- Xcode 26.6 and previous ARMv7 linker / ninja build still work.

WHAT CHANGES IN THE NATIVE BINARY:
- Defers CPython initialization, BPy modules and Python callbacks until after the first native Blender Viewport frame.
- The initial full draw omits header and right-side editors; they are rendered after Python loads. This is real Blender viewport, but input and tools are unavailable until Python finishes.
- Gives UIKit 180 ms of event-loop time after first native frame to make it visible before the main-thread Python import.
- Skips reading the recent-files history at startup (Recent Files list is not initialized on this iOS build).
- Marks all areas dirty after Python initialization to restore normal interface.
- Does not change UI39 Core's reduced module roster, scene storage, touch mapping or framebuffer resolution.
- All edits restricted to WM.c, WM_init_exit.c and WM_draw.c, backed up with .before-BLENDER3GS_UI40_NATIVE_FIRST_FRAME_20260925.

THIS IS A RISKY ARCHITECTURAL EXPERIMENT, NOT A GUARANTEED FIX.
The first draw before Python may hit an unexpected Python dependency and crash. No physical 3GS, SDK compilation or background retention test is available here. If a crash occurs, use the UNMODIFIED UI39 Core IPA for recovery. UI40 DOES NOT keep the process resident in background, solve white quads, or reduce the time for all final panels to load. A genuinely persistent background process requires a separately measured UIKit/jetsam diagnosis; never bypass iOS memory controls blindly.

ON MAC, one command to build and install:
  cd ~/Downloads && unzip -o Blender3GS_UI40_bundle.zip -d ~/Downloads && bash Blender3GS_UI40_BUILD_INSTALL.command
Check only:
  cd ~/Downloads && bash Blender3GS_UI40_BUILD_INSTALL.command --check-only
Resume AFTER sources patched and compilation/linking failed:
  cd ~/Downloads && bash Blender3GS_UI40_BUILD_INSTALL.command --resume
Install existing compiled IPA:
  cd ~/Downloads && bash Blender3GS_UI40_BUILD_INSTALL.command --install-only
Rollback (old native binary via old IPA):
  cd ~/Downloads && bash Blender3GS_UI39_BUILD_INSTALL.command --install-core

DEVICE LOG (second terminal BEFORE launching):
  idevicesyslog 2>&1 | tee ~/Downloads/Blender3GS-ui40-device.log | grep --line-buffered -E 'Blender3GS UI40 FAST|Blender3GS UI29 DRAW|Blender3GS UI17 PROPERTIES|Blender3GS UI31 PY|Blender3GS UI28 LIFE'

Interpretation:
  native_frame_done => first real 3D draw finished
  late_python_begin => second stage after the UIKit pump
  late_python_complete_ms => time for deferred interpreter + UI39 Core import
  panels=119 after staged registration is the prior reduced UI39 Core baseline, NOT 227 full Blender panels.

Do NOT install UI40 and expect project unsaved work to survive iOS killing the app. Save a .blend file before test. If install fails, shell exits without claiming success. IPA is signed in a fresh staging directory; UI39 original IPA never overwritten.
