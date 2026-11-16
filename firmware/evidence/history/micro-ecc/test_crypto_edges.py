#!/usr/bin/env python3
"""Reproduce known upstream P-256 defects; exit nonzero while unqualified.
Native compilation bypasses both the RV32 ABI adapter and Unicorn.
"""
import ctypes
import hashlib
import json
import os
import pathlib
import runpy
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(root / '.tools'))
from cryptography.hazmat.primitives.asymmetric import ec

fixture = runpy.run_path(str(root / 'test_rv32.py'))
u, call = fixture['u'], fixture['call']
k, p = fixture['k'], fixture['p']
source = root / 'vendor/micro-ecc-541b3a78026420a3e369c4c9281c396b5e531113/uECC.c'
library = root / 'build/micro-ecc-native.dylib'
compiler = os.environ.get('HOST_CC', '/opt/homebrew/opt/llvm/bin/clang')
flags = ['-shared', '-fPIC', '-O2', '-DuECC_PLATFORM=0', '-DuECC_WORD_SIZE=4',
         '-DuECC_SUPPORTS_secp160r1=0', '-DuECC_SUPPORTS_secp192r1=0',
         '-DuECC_SUPPORTS_secp224r1=0', '-DuECC_SUPPORTS_secp256k1=0',
         '-DuECC_SUPPORT_COMPRESSED_POINT=0']
subprocess.run([compiler, *flags, str(source), '-o', str(library)], check=True)
lib = ctypes.CDLL(str(library))
lib.uECC_secp256r1.restype = ctypes.c_void_p
lib.uECC_compute_public_key.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.uECC_compute_public_key.restype = ctypes.c_int
curve = call('uECC_secp256r1', [])
call('uECC_set_rng', [0])
order = int('ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551', 16)
scalars = [('0', 0), ('1', 1), ('2', 2), ('n-2', order-2), ('n-1', order-1), ('n', order)]
scalars += [('sha256-' + str(i), int.from_bytes(hashlib.sha256(('OpenDonz edge ' + str(i)).encode()).digest(), 'big') % (order-1) + 1) for i in range(8)]
rows = []
for label, scalar in scalars:
    key = scalar.to_bytes(32, 'big')
    valid = 0 < scalar < order
    expected = None
    if valid:
        point = ec.derive_private_key(scalar, ec.SECP256R1()).public_key().public_numbers()
        expected = (point.x.to_bytes(32, 'big') + point.y.to_bytes(32, 'big')).hex()
    native = ctypes.create_string_buffer(b'\xcc' * 64, 64)
    native_ret = lib.uECC_compute_public_key(key, native, lib.uECC_secp256r1())
    u.mem_write(k, key)
    u.mem_write(p, b'\xcc' * 64)
    direct_ret = call('uECC_compute_public_key', [k, p, curve])
    direct_out = bytes(u.mem_read(p, 64)).hex()
    u.mem_write(p, b'\xcc' * 64)
    adapter_ret = call('ecc_compute_public_p256r1', [k, p])
    adapter_out = bytes(u.mem_read(p, 64)).hex()
    passed = (native_ret == direct_ret == 1 and adapter_ret == 0 and
              native.raw.hex() == direct_out == adapter_out == expected) if valid else (
              native_ret == direct_ret == 0 and adapter_ret == p and
              native.raw.hex() == direct_out == adapter_out == 'cc' * 64)
    rows.append(dict(label=label, scalar=key.hex(), valid=valid, native_return=native_ret,
                     rv32_direct_return=direct_ret, rv32_adapter_return=adapter_ret,
                     native_output=native.raw.hex(), rv32_direct_output=direct_out,
                     rv32_adapter_output=adapter_out, reference_output=expected, passed=passed))
report = dict(status='PASS' if all(row['passed'] for row in rows) else 'FAIL',
              qualified=all(row['passed'] for row in rows),
              source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              elf_sha256=hashlib.sha256((root / 'build/u2f.elf').read_bytes()).hexdigest(),
              abi='uECC_compute_public_key returns int (1 success); adapter returns uint8_t * (NULL success, output pointer failure), not void',
              initialization='Fresh Unicorn fixture, explicit SP/RA/args, sentinel output, native RNG defaults NULL, RV32 RNG explicitly NULL; no startup or USB RTL tested',
              reference='cryptography/OpenSSL SECP256R1 public key derivation',
              root_cause='Known upstream Co-Z Montgomery ladder exceptional-point defect; reproduced directly on native host and RV32 without adapter',
              upstream=['https://github.com/kmackay/micro-ecc/issues/128', 'https://github.com/kmackay/micro-ecc/issues/167'],
              results=rows)
(root / 'build/crypto-edge.json').write_text(json.dumps(report, indent=2) + '\n')
for row in rows:
    print(row['label'], 'PASS' if row['passed'] else 'FAIL', 'native=', row['native_return'], 'rv32=', row['rv32_direct_return'])
sys.exit(0 if report['qualified'] else 1)
