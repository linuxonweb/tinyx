# TinyX keyboard input for the Wasm guest

The deployed Xfbdev was built from `tinycorelinux/tinyx` commit
`feab72ca891bc04b18763763e15ee4e532369cdf` (TinyX 1.3). The archived
linuxwasm Nix recipe is
`/mnt/p6/project/linux/.tmp-firefox-build/nix-local-store/nix/store/mzbhr58f5fk50b15xfrk68mwsdg4xs1c-source/tools/wasm/userspace/tinyx/package.nix`.
It applies the six `tinyx-*` patches listed there. Apply
`0001-wasm-evdev-keyboard.patch` after them for a normal target rebuild. It
opens `/dev/input/event0` nonblocking and sends EV_KEY press/release to KDrive,
while retaining the native VT path. The currently available workspace lacks
`nix`, target `libXfont.a`, and target `libfontenc.a`, so the source rebuild
could not be completed here.

The live archive instead uses a binary-specific WAT transform of the exact
pre-keyboard Xfbdev. With WABT 1.0.41, extract `bin/Xfbdev` from
`web/linux/initramfs-firefox.cpio.gz.backup-pre-evdev-keyboard-20260925`
(SHA-256 `cab3811d3b29129a2846a7c2097b6de829c56760dda2dda7a5f96895e7cda966`)
and run:

```sh
wasm2wat --enable-threads --enable-exceptions --enable-annotations Xfbdev -o Xfbdev.wat
python3 tools/wasm/userspace/tinyx/patch-packed-xfbdev-keyboard.py Xfbdev.wat Xfbdev-keyboard.wat
wat2wasm --enable-threads --enable-exceptions --enable-annotations --debug-names Xfbdev-keyboard.wat -o Xfbdev-keyboard.wasm
wasm-validate --enable-threads --enable-exceptions Xfbdev-keyboard.wasm
node -e 'new WebAssembly.Module(require("fs").readFileSync(process.argv[1]))' Xfbdev-keyboard.wasm
```

The transform checks the input WAT hash and produces Xfbdev-keyboard.wasm
SHA-256 `6cce82cafaf7c86ca9704e13283ecfac3bf41cf682f56c4b0dff01b1f624e796`.
It changes only the packed Xfbdev keyboard functions: opens the existing
`/dev/input/event0` path, translates 16-byte EV_KEY records into the original
TinyX KDrive input path, and retains VT fallback. Its hard-coded addresses and
function layout must not be used on any other TinyX build. The resulting
initramfs replaced only CPIO member `bin/Xfbdev`; the deployed archive hash
is recorded in the [archived Agents.md history](../../../../diary.md).
