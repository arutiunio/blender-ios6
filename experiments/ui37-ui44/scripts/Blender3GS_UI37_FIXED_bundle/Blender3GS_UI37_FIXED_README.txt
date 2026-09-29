UI37 FIX: correction of false WM marker guard and shell error propagation.

Actual UI35 source uses a boot-hide function and UI35 comment, but does not
contain the literal BLENDER3GS_UI35_NATIVE_BOOT_20260924 in wm.c. Original
UI37 stopped on valid UI36 source before its SHA-256 check. Corrected
preflight first checks the real markers, then exact SHA-256 UI36_WM.

No forced patch, rollback, hard-coded replacement of user source, or changes
to any installed app. The existing UI36 IPA stays intact. The stage and icon
experiments remain unverified until compiled and tested on the iPhone.

UNZIP & BUILD & INSTALL:
cd ~/Downloads && unzip -o Blender3GS_UI37_FIXED_bundle.zip -d ~/Downloads && bash Blender3GS_UI37_FIXED_BUILD_INSTALL.command

RESUME after changes applied:
cd ~/Downloads && bash Blender3GS_UI37_FIXED_BUILD_INSTALL.command --resume

INSTALL ONLY:
cd ~/Downloads && bash Blender3GS_UI37_FIXED_BUILD_INSTALL.command --install-only

If exact SHA still differs, STOP and report the printed actual hash, do not use --resume.
Collect source non-destructively:
cd ~/Downloads && zip -j Blender3GS-ui37-wm-diagnosis.zip blender-ios6-target/source/blender/windowmanager/intern/wm.c blender-ios6-target/source/blender/editors/interface/interface_icons.c
