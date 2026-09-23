#!/usr/bin/env python3
"""Repair cross-ABI RNA parameter strides in the iOS6 Blender experiment.

Build host makesrna first, regenerate target RNA, preserve the known dm_info
forward declaration, then compile bf_rna. Never touches the working IPA/binary.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

ROOT = Path.home() / "Downloads"
SRC = ROOT / "blender-ios6-target"
BUILD = ROOT / "blender-ios6-build-python"
HOSTBUILD = ROOT / "blender-ios6-host"
WORK = ROOT / "blender-ios6-python"
GENREL = Path("source/blender/makesrna/intern/makesrna.c")
MARKER = "Blender3GS: emit target ABI parameter sizes"
OLD = re.compile(
    r'(?m)^([ \t]*)fprintf\(f, "\\t_data \+= %d;\\n",\s*'
    r'rna_parameter_size_alloc\(dparm->prop\)\);[ \t]*$'
)
ANCHOR = "static void rna_def_function_funcs(FILE *f, StructDefRNA *dsrna, FunctionDefRNA *dfunc)"

HELPER = r'''/* Blender3GS: emit target ABI parameter sizes.
 * Host makesrna may run on arm64; generated code is compiled for armv7.
 * Keep this switch synchronized with rna_parameter_size() in rna_define.c.
 */
static void rna_parameter_size_alloc_print(FILE *f, PropertyRNA *parm)
{
    const PropertyType type = parm->type;
    const int len = parm->totarraylength;

    fprintf(f, "(");
    if (len > 0) {
        if (parm->flag & PROP_DYNAMIC) {
            fprintf(f, "sizeof(void *)");
        }
        else {
            switch (type) {
                case PROP_BOOLEAN:
                case PROP_INT:
                    fprintf(f, "sizeof(int) * %d", len);
                    break;
                case PROP_FLOAT:
                    fprintf(f, "sizeof(float) * %d", len);
                    break;
                default:
                    fprintf(f, "sizeof(void *)");
                    break;
            }
        }
    }
    else {
        switch (type) {
            case PROP_BOOLEAN:
            case PROP_INT:
            case PROP_ENUM:
                fprintf(f, "sizeof(int)");
                break;
            case PROP_FLOAT:
                fprintf(f, "sizeof(float)");
                break;
            case PROP_STRING:
                if (parm->flag & PROP_THICK_WRAP) {
                    StringPropertyRNA *sparm = (StringPropertyRNA *)parm;
                    fprintf(f, "sizeof(char) * %d", sparm->maxlength);
                }
                else {
                    fprintf(f, "sizeof(char *)");
                }
                break;
            case PROP_POINTER:
                if (parm->flag & PROP_RNAPTR) {
                    if (parm->flag & PROP_THICK_WRAP)
                        fprintf(f, "sizeof(PointerRNA)");
                    else
                        fprintf(f, "sizeof(PointerRNA *)");
                }
                else {
                    fprintf(f, "sizeof(void *)");
                }
                break;
            case PROP_COLLECTION:
                fprintf(f, "sizeof(ListBase)");
                break;
            default:
                fprintf(f, "sizeof(void *)");
                break;
        }
    }
    if (parm->flag & PROP_DYNAMIC)
        fprintf(f, " + sizeof(((ParameterDynAlloc *)NULL)->array_tot)");
    fprintf(f, ")");
}

'''


def run(command, log):
    print("COMMAND:", " ".join(map(str, command)), flush=True)
    with log.open("w") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        lines = log.read_text(errors="replace").splitlines()
        indexes = [i for i, line in enumerate(lines) if re.search(r"FAILED:|fatal error:|error:|ninja: error:", line)]
        print("\n=== FIRST ERRORS ===", flush=True)
        for i in indexes[:6]:
            print("\n".join(lines[max(0, i - 2):i + 6]), "\n---", flush=True)
        print("\n=== LAST 35 LINES ===", flush=True)
        print("\n".join(lines[-35:]), flush=True)
        raise SystemExit(f"STOP: command failed, full log: {log}")
    print("PASS:", log, flush=True)


def patch_preflight(path):
    if not path.is_file():
        raise SystemExit(f"STOP: missing generator source: {path}")
    s = path.read_text()
    if MARKER in s:
        if "rna_parameter_size_alloc_print(f, dparm->prop);" not in s:
            raise SystemExit(f"STOP: partial old patch in {path}")
        return None
    matches = list(OLD.finditer(s))
    if len(matches) != 1 or s.count(ANCHOR) != 1:
        print(f"Unexpected generator source: {path}")
        for i, line in enumerate(s.splitlines(), 1):
            if "rna_parameter_size_alloc" in line or "static void rna_def_function_funcs(" in line:
                print(f"{i}: {line}")
        raise SystemExit("STOP: source unchanged; send the lines printed above")
    m = matches[0]
    indent = m.group(1)
    # Construct without fragile multi-line literal matching.
    newcall = (
        indent + "{\n"
        + indent + '\tfprintf(f, "\\t_data += ");\n'
        + indent + "\trna_parameter_size_alloc_print(f, dparm->prop);\n"
        + indent + '\tfprintf(f, ";\\n");\n'
        + indent + "}"
    )
    s = s[:m.start()] + newcall + s[m.end():]
    s = s.replace(ANCHOR, HELPER + ANCHOR, 1)
    return s


def repair_dm_info(path):
    s = path.read_text()
    marker = "Blender3GS: forward declaration for RNA Object dm_info"
    if marker in s:
        print("RNA dm_info declaration already present")
        return
    prototype = list(re.finditer(
        r"(?m)^[ \t]*void[ \t]+rna_Object_dm_info[ \t]*\([^;\n]*\);[ \t]*$", s
    ))
    wrapper = re.search(r"(?m)^void[ \t]+Object_dm_info[ \t]*\(", s)
    if len(prototype) != 1 or wrapper is None or prototype[0].start() < wrapper.start():
        raise SystemExit("STOP: unexpected rna_object_gen.c shape, cannot safely restore dm_info declaration")
    backup = path.with_name("rna_object_gen.c.before-target-abi-fwd")
    if not backup.exists():
        shutil.copy2(path, backup)
    s = s[:wrapper.start()] + "/* " + marker + " */\n" + prototype[0].group().strip() + "\n\n" + s[wrapper.start():]
    path.write_text(s)
    print("PASS: restored RNA dm_info forward declaration")

print("========== 1. PREFLIGHT ACTUAL HOST SOURCES ==========", flush=True)
cache = HOSTBUILD / "CMakeCache.txt"
if not cache.is_file() or not (HOSTBUILD / "build.ninja").is_file():
    raise SystemExit(f"STOP: host build not found at {HOSTBUILD}")
if not (BUILD / "build.ninja").is_file():
    raise SystemExit(f"STOP: experimental ARMv7 build not found at {BUILD}")
cache_text = cache.read_text(errors="replace")
m = re.search(r"(?m)^CMAKE_HOME_DIRECTORY:INTERNAL=(.+)$", cache_text)
if not m:
    raise SystemExit("STOP: CMAKE_HOME_DIRECTORY absent in host CMakeCache.txt")
host_source = Path(m.group(1).strip()) / GENREL
mobile_source = SRC / GENREL
host_tool = HOSTBUILD / "bin/makesrna"
if not host_tool.exists():
    raise SystemExit(f"STOP: host generator missing: {host_tool}")
paths = list(dict.fromkeys((host_source.resolve(), mobile_source.resolve())))
plans = [(path, patch_preflight(path)) for path in paths]
for path, content in plans:
    print("HOST SOURCE:" if path == host_source.resolve() else "TARGET SOURCE:", path, "ALREADY PATCHED" if content is None else "READY", flush=True)

print("\n========== 2. PATCH ONLY VERIFIED GENERATOR FILES ==========", flush=True)
for path, new_content in plans:
    if new_content is None:
        continue
    backup = path.with_name("makesrna.c.before-ios6-target-size")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(new_content)
    print("PATCHED:", path, "BACKUP:", backup, flush=True)

WORK.mkdir(parents=True, exist_ok=True)
print("\n========== 3. REBUILD ACTUAL HOST MAKESRNA ==========", flush=True)
run(["ninja", "-C", str(HOSTBUILD), "-j4", "makesrna"], WORK / "rebuild-host-makesrna-v2.log")
if not host_tool.is_file():
    raise SystemExit("STOP: host makesrna executable not produced")
subprocess.run(["file", str(host_tool)], check=True)
# The custom command in the iOS CMake project depends on this host binary.
os.utime(host_tool, None)

print("\n========== 4. REGENERATE ARMv7 RNA (NO FILE DELETION) ==========", flush=True)
run(["ninja", "-C", str(BUILD), "-j1", "source/blender/makesrna/intern/rna_ui_gen.c"], WORK / "regenerate-rna-v2.log")
rna_dir = BUILD / "source/blender/makesrna/intern"
ui = rna_dir / "rna_ui_gen.c"
obj = rna_dir / "rna_object_gen.c"
if not ui.is_file() or not obj.is_file():
    raise SystemExit("STOP: generated RNA source missing")
s = ui.read_text(errors="replace")
start = s.find("void UILayout_operator_call(")
if start < 0:
    raise SystemExit("STOP: UILayout_operator_call missing")
end = s.find("\n}", start)
chunk = s[start:end + 2]
print(chunk, flush=True)
if chunk.count("_data += (sizeof(char *));") != 2 or re.search(r"_data \+= 8;", chunk):
    raise SystemExit("STOP: target pointer stride not correct. bf_rna NOT compiled")
print("PASS: RNA operator string strides are target-size expressions", flush=True)

print("\n========== 5. PRESERVE KNOWN OLD-BLENDER FORWARD DECLARATION ==========", flush=True)
repair_dm_info(obj)

print("\n========== 6. COMPILE ARMv7 BF_RNA ==========", flush=True)
run(["ninja", "-C", str(BUILD), "-j4", "bf_rna"], WORK / "rebuild-bf-rna-v2.log")
print("\nSUCCESS: corrected target-ABI RNA compiled", flush=True)
print("Working Touch v2 binary and IPA were not modified.", flush=True)
print("Next: relink Python experimental binary, then package and test.", flush=True)