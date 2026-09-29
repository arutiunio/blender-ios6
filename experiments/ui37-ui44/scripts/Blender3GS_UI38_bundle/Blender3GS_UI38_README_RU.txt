UI38 = aggressive first-real-frame repack of the already-built UI37 IPA.
It does not require compiling Blender, nor does it overwrite or modify UI37.

1. cd ~/Downloads && unzip -n Blender3GS_UI38_bundle.zip -d ~/Downloads && bash Blender3GS_UI38_BUILD_INSTALL.command
2. Only install: cd ~/Downloads && bash Blender3GS_UI38_BUILD_INSTALL.command --install-only
3. Repack generated output intentionally: cd ~/Downloads && bash Blender3GS_UI38_BUILD_INSTALL.command --repack
4. Device logs: idevicesyslog 2>&1 | tee ~/Downloads/Blender3GS-ui38-device.log | grep --line-buffered -E 'Blender3GS UI37 STAGE|Blender3GS UI29 DRAW|Blender3GS UI17 PROPERTIES|Blender3GS UI31 PY|Blender3GS UI28 LIFE|Blender3GS UI35 BOOT'

This experiment includes the original full Python payload but imports fewer UI modules
before first frame, then TWO deferred modules per old UI37 WM step. It preserves
full actual Blender editor, CPU picking and native boot cover. Panels may appear
in stages. Verify that final panel count reaches 227 and that input still works.

Background Manager (iOS 6 jailbreak tweak) can keep a selected app resident:
Settings > Background Manager > Each App > Add Item > Blender Py > Background
Mode: Background / Forced. Optional Auto Launch only if stable. Availability of
an authentic working package in 2026 is not verified. Do not install random debs.
GL calls MUST remain paused while backgrounded, even if tweak is installed.

No promise of instant real initialization, no guarantee against jetsam.
