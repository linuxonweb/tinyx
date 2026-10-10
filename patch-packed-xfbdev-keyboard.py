"""Apply the evdev keyboard shim to the pinned TinyX 1.3 packed Wasm WAT.

The address/function constants are from the exact Xfbdev image documented in
README.md. The input hash guard prevents applying this binary-specific fallback
to an ABI-incompatible build. Prefer 0001-wasm-evdev-keyboard.patch when the
complete target Nix toolchain is available.
"""
import argparse
import hashlib
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('input_wat', type=Path)
parser.add_argument('output_wat', type=Path)
args = parser.parse_args()
raw = args.input_wat.read_bytes()
expected = 'dede96e6442e4a01fc3418a86d7646fc007b9e03679705326e1ba8a2ecf9e572'
actual = hashlib.sha256(raw).hexdigest()
if actual != expected:
    raise SystemExit(f'input WAT SHA mismatch: {actual}; expected {expected}')
s = raw.decode('utf-8')

def replace_func(name, old, new):
    global s
    start = s.index(f'  (func ${name} ')
    end = s.find('\n  (func $', start + 2)
    if end < 0:
        raise RuntimeError(f'missing end for {name}')
    body = s[start:end]
    if body.count(old) != 1:
        raise RuntimeError(f'{name}: replacement count {body.count(old)}')
    s = s[:start] + body.replace(old, new, 1) + s[end:]

replace_func('LinuxKeyboardInit',
'''    i32.const 0
    i32.load offset=8730860
    local.set 1''',
'''    i32.const 8393623
    i32.const 2048
    i32.const 0
    call $open
    local.tee 1
    i32.const 0
    i32.lt_s
    if
      i32.const 0
      i32.load offset=8730860
      local.set 1
    end
    local.get 1
    global.set $WasmKeyboardFd''')
# The inlined registration path reloads LinuxConsoleFd twice after it stores the
# new fd. Both callback setup and enable must use the registered evdev fd.
start = s.index('  (func $LinuxKeyboardInit ')
end = s.index('\n  (func $', start + 2)
body = s[start:end]
old = 'i32.const 0\n      i32.load offset=8730860'
parts = body.split(old)
assert len(parts) == 4, len(parts)
body = parts[0] + old + parts[1] + 'global.get $WasmKeyboardFd' + parts[2] + 'global.get $WasmKeyboardFd' + parts[3]
s = s[:start] + body + s[end:]
replace_func('LinuxKeyboardRead',
'''        call $read
        local.tee 3''',
'''        call $WasmEvdevKeyboardRead
        local.tee 3''')
replace_func('LinuxKeyboardEnable',
'''    (local i32)
    global.get $__stack_pointer''',
'''    (local i32)
    local.get 0
    global.get $WasmKeyboardFd
    i32.eq
    if
      local.get 0
      return
    end
    global.get $__stack_pointer''')
replace_func('LinuxKeyboardDisable',
'''    (local i32)
    global.get $__stack_pointer''',
'''    (local i32)
    local.get 0
    global.get $WasmKeyboardFd
    i32.eq
    if
      return
    end
    global.get $__stack_pointer''')
replace_func('LinuxKeyboardFini',
'''    (local i32)
    global.get $__stack_pointer''',
'''    (local i32)
    global.get $WasmKeyboardFd
    i32.const 0
    i32.ge_s
    if
      i32.const 0
      i32.load offset=8730792
      i32.const 0
      call $KdUnregisterFds
      global.get $WasmKeyboardFd
      call $close
      drop
      i32.const -1
      global.set $WasmKeyboardFd
      return
    end
    global.get $__stack_pointer''')
marker = '  (global $__stack_pointer (mut i32) (i32.const 8388608))'
if s.count(marker) != 1: raise RuntimeError('stack global marker')
s = s.replace(marker, marker + '\n  (global $WasmKeyboardFd (mut i32) (i32.const -1))', 1)
shim = '''  (func $WasmEvdevKeyboardRead (type 8) (param i32 i32 i32) (result i32)
    (local i32 i32)
    local.get 0
    global.get $WasmKeyboardFd
    i32.ne
    if
      local.get 0
      local.get 1
      local.get 2
      call $read
      return
    end
    global.get $__stack_pointer
    i32.const 16
    i32.sub
    local.tee 3
    global.set $__stack_pointer
    block
      loop
        local.get 0
        local.get 3
        i32.const 16
        call $read
        local.tee 4
        i32.const 16
        i32.ne
        br_if 1
        local.get 3
        i32.load16_u offset=8
        i32.const 1
        i32.ne
        br_if 0
        local.get 3
        i32.load16_u offset=10
        i32.const 128
        i32.ge_u
        br_if 0
        local.get 3
        i32.load offset=12
        i32.const 2
        i32.gt_u
        br_if 0
        local.get 1
        local.get 3
        i32.load16_u offset=10
        local.get 3
        i32.load offset=12
        i32.eqz
        i32.const 7
        i32.shl
        i32.or
        i32.store8
        i32.const 1
        local.set 4
        br 1
      end
    end
    local.get 3
    i32.const 16
    i32.add
    global.set $__stack_pointer
    local.get 4
    i32.const 0
    i32.gt_s
    local.get 4
    i32.const 0
    select)
'''
marker = '  (func $LinuxKeyboardRead '
if s.count(marker) != 1: raise RuntimeError('read function marker')
s = s.replace(marker, shim + marker, 1)
args.output_wat.write_text(s)
print(args.output_wat)
