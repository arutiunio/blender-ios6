# UI19 handoff and device-test checkpoint (2026-09-24)

The local terminal history reports a successful ARMv7 build, link and package of
`Blender3GS-python-ui-v19-hybrid-touch.ipa`, followed by an SCP transfer and
`ios6-installer` invocation. It does **not** include a visual/interaction test
of that latest build. UI17 was previously applied; its patch script intentionally
refuses to apply again. The actual modified UI19 C/C++ source is **not yet in
this repository**. Do not run historical UI17/UI18 patch scripts again.

## Collect the exact current sources

From the development Mac, download `scripts/capture-ui19-source.py` and run:

```sh
cd ~/Downloads
python3 capture-ui19-source.py --check-only
python3 capture-ui19-source.py
```

This creates `~/Downloads/Blender3GS-ui19-source-handoff.zip` containing the
current UI, font, GHOST/UIKit, screen, and window-manager source files plus
SHA-256 hashes/patch markers. It does not alter the build or working source,
overwrite an existing ZIP, include IPA bytes or full syslogs, or upload anything.
Inspect the ZIP and share it privately for source-level debugging; this subset
is **not** a complete corresponding-source release.

If the collector warns that the UI19 marker is missing in either
`GHOST_WindowIOS.mm` or `wm_files.c`, stop before any further patching and
compare the actual source tree with the terminal history.

## Test the installed UI19 on the physical 3GS

1. Launch `Blender Py` and capture a screenshot of the default scene and Properties.
2. Check tapping a Properties tab, selecting the cube, opening Add, dragging the
   viewport, and trying modifier controls separately. Report visible behavior,
   not merely successful installation.
3. Record a small, redacted syslog excerpt for `Blender3GS UI17 PROPERTIES` and
   any application crash, if one occurs. Do not publish unreviewed complete logs.

Once the exact source ZIP and device observation are available, make a narrowly
scoped UI20 patch on the **current UI19** source, validate the real target
anchors, retain backups, and package under a new filename. Do not infer the
missing current source from older historical patch scripts.
