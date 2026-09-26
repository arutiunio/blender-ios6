# Project status

Last updated: 2026-09-26 (latest documented device capture: 2026-09-25). All statuses below describe **reported physical iPhone 3GS tests**, not CI or an automated hardware test farm.

| Milestone | Result |
| --- | --- |
| Native Blender 2.64 viewport | Visible and interactive on iPhone 3GS. |
| Embedded Python / RNA | Python-enabled build loads; ARMv7 RNA pointer strides were corrected. |
| Native Add popup | Text was restored sufficiently to show entries including Mesh, Curve, Surface and Camera. |
| Touch controls | Experimental trackpad-like controls implemented and tested. |
| Icon atlas | The iOS GLES2 icon texture is created successfully in later device logs. |
| Mobile layout | UI16 resizes the existing native Properties area from approximately 64 px to approximately 184 px. |
| Properties controls | **Incomplete:** missing labels/icons and panel content. Modifier, render and material workflows are not yet validated. |
| Stability/performance | No comprehensive benchmark, memory profiling or long-session regression test yet. |

## Verified issues and lessons

- The embedded RNA wrapper generator used host-sized pointer strides; these had to be emitted as target-side `sizeof(...)` expressions.
- The custom Python 3.3 runtime needed its `atexit` builtin registered before `Py_Initialize`.
- Some earlier test versions crashed because a GLEW function pointer for `glActiveTexture` was not initialized. Later code avoids those unsafe calls.
- The original desktop startup layout allocated only a very narrow strip to Properties. A startup-only mobile layout change expanded it without replacing the 3D viewport.
- Correct icon texture creation does **not** prove that every icon or label is visible. Investigate the Properties editor's region layout, text draw path, context and scroll behavior separately.

## Next milestones

1. Restore readable native Properties tabs and visible panel contents.
2. Verify selection of Render, Object, Modifiers and Material contexts.
3. Add a modifier to the default cube on real hardware.
4. Verify render settings and a simple output.
5. Audit code changes into a clean patch set against the exact Blender 2.64 base.
6. Produce a source-matched pre-alpha release and an independent clean build.

Screenshots and device syslogs should be attached to issues with the matching version and Mach-O UUID, with personal information redacted.

## September 25 UI37–UI44 milestone (newer than the historical status above)

See [the UI37–UI44 experiment record](../experiments/ui37-ui44/README.md), [original-asset SHA-256 manifest](../experiments/ui37-ui44/SHA256SUMS), and the [Mac artifact sync script](../scripts/sync-ui37-ui44-from-mac.sh).

- **UI36 full-profile baseline:** on-device logs recorded 227 Properties panels. Subsequent Core builds intentionally load a reduced set.
- **UI40/UI41 fast launch:** a real native Viewport frame is presented *before* embedded Python initialization. In the UI41 device log, the first draw took approximately one second after Blender's initial scene/layout setup; Python still runs later on the UI thread for about 3.5–3.9 seconds. Subsequent launches may be faster from warm caches; changed process IDs mean persistence through Home is not demonstrated.
- **UI43 screenshot-tested graphics isolation:** suppressing the old Camera/Lamp viewport draw path removed the giant white triangle and large camera rectangle. Cross-editor white lines and icon artifacts remain. Camera/Lamp viewport geometry is temporarily hidden, not fixed.
- **UI44:** experimental per-icon clipping, editor GL-state isolation and simple Camera/Lamp markers have been prepared; no confirmed phone test or screenshot yet.
- **Outstanding:** complete native UI and icon rendering, background process lifetime, Python's main-thread stall, clean-source reproducibility, saving/rendering workflow validation. UI39 Core has 119 registered panels in tested logs, not the earlier 227.

Never publish unredacted full device logs from this session; they include account-identifying entries. Source/IPA release still requires complete corresponding-source audit and toolchain/dependency inventory.
