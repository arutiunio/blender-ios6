# What to send for the source release

The git repository currently contains English documentation and archived **historical** patch scripts. The **actual modified source tree and source-matched IPA have not yet been uploaded**. Please send the files below from the Mac that built and tested the application.

## 1. Exact modified source tree (required)

Create a source archive from the existing tree, not a clean Blender checkout:

```sh
cd "$HOME/Downloads"
tar -czf Blender3GS-current-source.tar.gz \
  --exclude='.git' \
  --exclude='*.before-*' \
  --exclude='__pycache__' \
  --exclude='*.o' \
  --exclude='*.a' \
  --exclude='*.dSYM' \
  --exclude='*.log' \
  blender-ios6-target
```

Do not delete or change the local working tree. The archive should include GHOST/UIKit, all modified Blender C/C++ files, headers, source resources and CMake files. Keep license and copyright files. If the archive is too large to attach, use a private file transfer or push the source from the Mac with git, then provide the exact commit SHA.

## 2. Exact build and packaging scripts (required)

Please supply these files, or one ZIP containing them:

```text
~/Downloads/blender-link-ios-python-v3.py
~/Downloads/Blender3GS-package-python.py
~/Downloads/blender-ios6-python/Blender3GS-package-ui-v*.py
~/Downloads/Blender3GS-*.py
~/Downloads/Blender3GS-shot.sh
```

Also include the scripts used to build CPython 3.3.x, GL4ES, the host RNA generator and the iOS SDK/toolchain configuration, if available. A patch script is not a substitute for the final edited source file.

## 3. Tested binary and package base (required)

Provide the exact IPA installed and tested on the iPhone, **not merely the newest file by name**. Supply the earlier `Blender3GS-touch-v2.ipa` privately too if the current packager still uses it as its resource base.

Record the IPA checksum:

```sh
shasum -a 256 "$HOME/Downloads/NAME-OF-TESTED-BUILD.ipa"
```

Do not place binary IPA files into normal git commits: use GitHub Release assets when the matching source is ready.

## 4. Dependency/build manifest (required for reproducibility)

Supply the versions/source URLs/licenses of CPython, GL4ES and the other libraries in `~/Downloads/ios-deps/`; exact compiler and linker flags; CMake configuration; and any locally compiled Objective-C/C objects needed by the linker. We cannot infer these correctly from an IPA.

## 5. Optional public release materials

- One clean screenshot showing the viewport and one showing the current Properties editor.
- A short device-tested feature/known-issues list.
- Redacted crash logs if a specific issue is still being tracked.

**Privacy:** Do not upload SSH keys, passwords, provisioning profiles, signing identities, Apple account files, device identifiers, personal mail/log data or an unreviewed `CMakeCache.txt` to a public repository. Review source archives for accidental secrets before uploading.

Once these inputs are available, organize the **real** source into `ios/`, `patches/`, `scripts/`, and any required vendored/externally fetched dependencies; reconcile licenses and publish a pre-alpha release with source, IPA and checksums.
