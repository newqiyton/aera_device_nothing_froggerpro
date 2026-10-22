#!/usr/bin/env python3
"""Check the packaged runtime; no device writes or runtime success claims."""
import argparse
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("ramdisk", type=Path)
args = parser.parse_args()
root = args.ramdisk.resolve()
tree = Path(__file__).resolve().parents[1]

assert re.search(r"^AERA_SCREEN_H\s*:=\s*2400$", (tree / "aera.mk").read_text(), re.M)
qcom = (root / "init.recovery.qcom.rc").read_text()
assert "import /init.recovery.wifi.rc" in qcom
assert "init.recovery.qcom_decrypt" not in qcom
for filename in ("init.recovery.qcom_decrypt.rc", "init.recovery.qcom_decrypt.fbe.rc"):
    assert not (root / filename).exists(), f"Stale legacy crypto init: {filename}"
crypto = (root / "init.recovery.encryption.rc").read_text()
assert crypto.count("service prepdecrypt ") == 1
assert (root / "system/bin/prepdecrypt.sh").is_file()
se = (root / "vendor/etc/init/android.hardware.secure_element_gto.rc").read_text()
assert "seclabel u:r:recovery:s0" in se
assert "start gto_secure_element_aidl_service" not in se
assert not (root / "vendor/etc/init/android.hardware.boot-service.qti.recovery.rc").exists()
touch = (root / "system/bin/runatboot.sh").read_text()
assert "focaltech_fts" in touch and '"$TOUCH_READY" = 1' in touch

search = [root / directory for directory in (
    "vendor/lib64", "system/lib64", "system/lib64/bootstrap", "system_ext/lib64",
)]
queue = [root / "vendor/lib64" / name for name in (
    "egl/libEGL_adreno.so", "egl/libGLESv2_adreno.so",
    "egl/libGLESv1_CM_adreno.so", "libllvm-glnext.so", "libllvm-qgl.so",
    "libllvm-qcom.so", "libadreno_utils.so", "libgsl.so",
)]
visited = set()
missing = set()
while queue:
    path = queue.pop()
    if path in visited:
        continue
    visited.add(path)
    assert path.is_file(), f"Missing GPU runtime library: {path}"
    result = subprocess.run(["readelf", "-d", str(path)], capture_output=True, text=True, check=True)
    for name in re.findall(r"Shared library: \[(.*?)\]", result.stdout):
        target = next((directory / name for directory in search if (directory / name).is_file()), None)
        if target is None:
            missing.add(f"{path.name} -> {name}")
        else:
            queue.append(target)
assert not missing, "Unresolved GPU dependencies:\n" + "\n".join(sorted(missing))

# Include GNU IFUNC exports (readelf prints their type as "<OS specific>: 10")
# and linker-provided __loader_* entry points when checking strong symbols.
provided = set()
required = {}
for path in visited | {root / "system/bin/linker64"}:
    assert path.is_file(), f"Missing runtime linker: {path}"
    symbols = subprocess.run(["readelf", "--dyn-syms", "--wide", str(path)],
                             capture_output=True, text=True, check=True).stdout
    for binding, section, name in re.findall(
            r"\b(GLOBAL|WEAK)\s+(?:DEFAULT|PROTECTED|HIDDEN)\s+(\S+)\s+(\S+)", symbols):
        name = name.split("@")[0]
        if section != "UND":
            provided.add(name)
        elif binding == "GLOBAL":
            required.setdefault(path.name, set()).add(name)
unresolved = {name: sorted(symbols - provided) for name, symbols in required.items()
              if symbols - provided}
assert not unresolved, f"Unresolved GPU strong symbols: {unresolved}"
print(f"PASS: UI reference height, init cleanup, touch guard and {len(visited)} GPU dependency ELFs")
