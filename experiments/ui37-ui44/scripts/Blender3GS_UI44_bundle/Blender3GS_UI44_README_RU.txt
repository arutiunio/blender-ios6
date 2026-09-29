Blender3GS UI44 FOCUS — experimental source patch atop successfully built UI43.

First-time Mac command:
cd ~/Downloads && unzip -o Blender3GS_UI44_bundle.zip -d ~/Downloads && bash Blender3GS_UI44_BUILD_INSTALL.command

STOP during preflight: do NOT run --resume; send STOP output.
After BACKUP + PATCH if compilation/relink fails: bash ~/Downloads/Blender3GS_UI44_BUILD_INSTALL.command --resume
After successful ARMv7 build if packaging fails: bash ~/Downloads/Blender3GS_UI44_BUILD_INSTALL.command --package-only
To install ready IPA: bash ~/Downloads/Blender3GS_UI44_BUILD_INSTALL.command --install-only
Rollback to UI43 without recompilation: bash ~/Downloads/Blender3GS_UI44_BUILD_INSTALL.command --rollback

Changes:
- Preserves UI40/41 native first frame + late Python (UI39 Core scripts untouched).
- Bounded GL scissor / depth / face-cull state at region boundary, restores previous states.
- Per-icon scissor on UI43 tiny texture quad path to prevent overruns into adjacent regions.
- Camera/Lamp display as tiny world-space three-axis line crosses, never legacy filled helper polygons.
- This is a device candidate. Actual rendering and compilation need Mac + iPhone test.

Markers:
Blender3GS UI44 FOCUS: scoped_region_GL=1
Blender3GS UI44 FOCUS: icon_scissor=1
Blender3GS UI44 FOCUS: safe_camera_lamp_crosses=1

Output: ~/Downloads/Blender3GS-python-ui-v44-focus.ipa ; original UI43 IPA not modified.
IMPORTANT: per-icon clipping uses region-local coordinates. If icons vanish or become cut off,
rollback UI43 and send screenshot/log. Do not tweak coordinate math blindly.
