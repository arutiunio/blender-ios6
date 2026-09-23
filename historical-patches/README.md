# Historical development scripts

These files are preserved as a **development history**, not as a one-command installer or a clean source distribution. Most scripts mutate an existing Blender 2.64 source checkout, look for exact markers left by a previous experimental version, and assume locally named build directories. They must be applied only to the matching source state.

**Important:** The canonical, reproducible source snapshot is still pending. In particular, the latest modified C/C++/Objective-C sources, complete linker input, CMake configuration, third-party dependency sources/manifests and matching IPA are not reconstructed by these scripts alone.

The v13 test added an unsafe `glActiveTexture` call in the project's GLEW path and crashed on device; the v14 patch was written to address that regression. Intermediate font/scissor tests are diagnostic history and should not be mistaken for final fixes. Later UI17/UI18 scripts do not establish successful physical-device testing by their presence in this folder.

See [status](../docs/STATUS.md), [build notes](../docs/BUILD.md), and [release checklist](../docs/RELEASE.md).