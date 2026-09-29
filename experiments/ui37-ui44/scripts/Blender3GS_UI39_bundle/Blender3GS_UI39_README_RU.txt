Blender3GS UI39 — controlled Core-vs-Full Python startup A/B experiment.

Prerequisite on Mac: existing ~/Downloads/Blender3GS-python-ui-v38-fast-first-frame.ipa.
This experiment repackages UI38 only; no Blender source changes or ARMv7 compilation.

Modes:
CORE (CFBundleVersion 39): auto-register 18/47 original bl_ui modules and
6/20 bl_operators modules. Only 5 UI and 2 operator modules load before
the first frame; the remaining selected core modules load just after it. Retains native scene, View3D, Outliner, File Browser,
Object, Render, Material, Modifier, Mesh, Camera, Lamp, Scene, World and selected
3D editing operators. UI modules for game engine, smoke/fluid/dynamic paint,
movie clip editor, video sequencer, audio speaker editor, NLA, node editor,
physics, rig and less relevant editors are intentionally not auto-registered.
They remain physically packaged, so a later build can restore them.

FULL (CFBundleVersion 40): all 47/20 modules retained; control for testing
whether cold startup script directory enumeration and addon scanning matter.

Both modes patch bpy.utils.load_scripts: when cold-starting with NO enabled
add-ons, avoid scanning every script path and run the exact known default
startup packages directly. When add-ons are enabled, or scripts are reloaded,
the stock startup path remains. If your custom startup scripts must run on
cold start, use UI38 instead: the fast path intentionally ignores user startup
scripts when add-ons are disabled. Validate compatibility after installation.

The default installed IPA is CORE. Both modes share Blender's bundle ID and
replace each other. They do not install two separate icons.

Download UI39 ZIP into ~/Downloads, connect iPhone 3GS by USB, run:
  cd ~/Downloads && unzip -o Blender3GS_UI39_bundle.zip -d ~/Downloads && bash Blender3GS_UI39_BUILD_INSTALL.command --core

To build and install FULL control:
  cd ~/Downloads && bash Blender3GS_UI39_BUILD_INSTALL.command --full

Install already built IPA without rebuilding:
  cd ~/Downloads && bash Blender3GS_UI39_BUILD_INSTALL.command --install-core
  cd ~/Downloads && bash Blender3GS_UI39_BUILD_INSTALL.command --install-full

Capture log in second Terminal BEFORE launching Blender:
  idevicesyslog 2>&1 | tee ~/Downloads/Blender3GS-ui39-device.log | grep --line-buffered -E 'Blender3GS UI3[017589]|Blender3GS UI28 FRAME|Blender3GS UI17 PROPERTIES|Blender3GS UI37 STAGE|Blender3GS UI28 LIFE'

Analyze log:
  cd ~/Downloads && python3 Blender3GS_UI39_ANALYZE.py Blender3GS-ui39-device.log

Compare same conditions / cold boot / warm boot and FULL vs CORE:
UI31 PY complete, first real frame (= WM init + first frame draw), final
registered panel count, and selection/save/menu behavior. Existing UI38 IPA
is untouched. Roll back through Blender3GS_UI38_BUILD_INSTALL.command --install-only.

IMPORTANT: no real-device speed or functional validation yet. Not a background
retention fix; iOS can still kill the app. White right-side quads remain a
separate graphics issue. Do not trust a single successful install as a pass.
