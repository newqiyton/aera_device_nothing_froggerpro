# FroggerPro Wi-Fi bring-up

This is a device-tree-only correction of the initial Wi-Fi setup. No common
AERA source changes or replacement firmware/kernel modules are required.

## Stock evidence

- Stock `vendor/etc/init/init.vendor.wlan.rc` starts integrated WPSS with
  `/sys/kernel/icnss/wlan_en_delay` and `/sys/kernel/icnss/wpss_boot`.
- The Kera base DTB requests `qca6750/wpss.mdt`. The dumped active firmware
  package (`modem.img`) contains that image and QCA6750 BDF/regulatory files.
- Stock `qca_cld3_qca6750.ko` depends on `icnss2`, `cfg80211`,
  `cnss_prealloc`, `cnss_utils`, `cnss_nl` and `qcom_va_minidump`.
- The copied QCA6750 INI matches the dump byte-for-byte and is retained.
  Its firmware aliases and per-device MAC path under persist are also retained.

The old recovery configuration had an unimported Wi-Fi RC, no deferred WLAN
host-driver list, and a Lighthouse-style CNSS/Peach `fs_ready` path. Loading
only `wlan_firmware_service` and `rmnet_wlan` cannot create `wlan0`.

## Changes

- Import Wi-Fi init, stage the ordered WLAN dependency list from the installed
  ROM, and start WPSS after the post-decryption module stage.
- Include `socinfo`, `qcom_iommu_util` and `pinctrl-msm` in the early module
  request list; ICNSS needs these vendor-boot prerequisites before its deferred
  module can bind. Their dependencies are resolved by the early module loader.
- Remount active-slot modem firmware and original persist data read-only after
  decryption releases them. Use `/vendor/firmware_mnt/image` for firmware lookup.
- Wait for a real `wlan0` before declaring driver readiness; bound the waiter
  to 60 seconds and keep the normal AERA supplicant service/control socket.
- Remove the two stale bundled Wi-Fi-related modules from the ramdisk and
  their unconditional boot-script insertion. Existing haptic/touch modules
  are not changed by this Wi-Fi correction.
- Keep all recovery settings in BoardConfig-included `aera.mk` and
  `aera_config.mk`, convert supported legacy flags to AERA names, enable
  adaptive UI sizing, and retain the existing English/crypto/haptics settings.
- `AERA_ENABLE_WLAN := 1` was already present. It is retained and tested;
  it was not the missing driver/init wiring.

## Offline checks

From this tree's root:

```
make -f tests/aera_flags.mk AERA_SOURCE=/path/to/AERA_16.0
python3 tests/check_wifi.py /path/to/extracted/FroggerPro
/path/to/AERA_16.0/out/host/linux-x86/bin/host_init_verifier recovery/root/init.recovery.wifi.rc
```

These checks do **not** prove a successful boot or Wi-Fi connection. The
multi-device stock DTBO contains other WLAN variants; a recovery kernel log
must confirm the running FroggerPro board binds to the QCA6750/ICNSS path.
Do not enable every QCA host-driver variant at once to hide a mismatch.

## Runtime corrections from the first AERA log

- Set the adaptive reference height to 2400 for the 1260x2800 display, yielding
  a 1440x3200 logical canvas rather than 1440x3733.
- Include stock `libadreno_utils` and `libgsl`, plus source-built
  `libnativewindow`, and audit the packaged GPU dependency closure.
- Keep the shared `prepdecrypt.sh`, but declare its service locally and remove
  the legacy HIDL crypto init templates. Preserve the existing vendor
  KeyMint/Gatekeeper stack and preparation trigger.
- Start qseecomd after filesystem setup. Give the secure-element service an
  explicit recovery domain, because init's missing-transition check still
  applies in permissive mode. Retain one boot-control service declaration.
- Skip fallback touchscreen insertion when a ROM touchscreen module is already
  loaded (the tester kernel provides `focaltech_fts`). Preserve the stock
  fallback for kernels without a loaded touchscreen driver.

After building, run `python3 tests/check_runtime.py /path/to/recovery/root`.
Passing this ELF/file audit does not prove hardware GPU initialization or
successful decryption; those still need the next device log.

## USB/ADB corrections

The recovery log showed common init binding `g1` successfully, followed by a
second device action changing IDs and failing another bind with `EBUSY`.
The old device RC also mounted ADB/fastboot FunctionFS a second time, created
children of a nonexistent `g2`, and bound the gadget unconditionally at boot.

The device RC now selects configfs in early-init and resolves the boot-supplied
controller before common init's fs actions. The known fallback `a600000.dwc3`
is confirmed by the recovery log and the stock `a600000.ssusb` controller path.
Stock USB setup was used as a controller/function reference, not copied as a
second Android USB HAL alongside recovery's own gadget management.

Common init remains the sole owner of ADB/sideload/fastboot bindings and their
FunctionFS mounts. The device RC adds only MTP, requires both descriptor-ready
signals for MTP+ADB, and uses one vendor ID with mode-specific product IDs from
`system.prop`. The existing peripheral-role initialization is retained but
moved before binding, with a bounded wait for UDC registration. It no longer
forces ADB again at boot (which could overwrite another requested mode).

Run `python3 tests/check_usb.py /path/to/AERA_16.0`, and repeat with
`--ramdisk /path/to/recovery/root` after building. This is an action/packaging
audit, not an on-device USB enumeration test.

## Device validation

Test a clean boot, complete decryption (or boot without a screen lock), then
turn Wi-Fi on, scan, connect to WPA2 and WPA3 networks, obtain DHCP/DNS, and
turn Wi-Fi off/on. Also check the recovery/fastbootd round trip.

Capture these after a failed attempt:

```
adb shell getprop post.decrypt.modules
adb shell getprop wifi.driver.ready
adb shell getprop init.svc.wpa_supplicant
adb shell uname -r
adb shell cat /proc/modules
adb shell ls -l /sys/kernel/icnss /sys/class/net
adb shell cat /proc/mounts
adb shell dmesg > froggerpro-wifi-dmesg.txt
adb logcat -b all -d > froggerpro-wifi-logcat.txt
adb pull /tmp/recovery.log froggerpro-recovery.log
```

The log should show staged/loaded ICNSS and QCA6750 modules, WPSS firmware
startup, `wlan0`, supplicant control readiness and DHCP. Missing symbols,
kernel-version mismatches or different hardware binding need a tester log,
not another device's prebuilt modules.
