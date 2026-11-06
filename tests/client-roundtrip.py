#!/usr/bin/env python3
"""Full-chip DOS client tests. Optional argument: extracted Phyton Core for cross-checks."""
# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib
import random
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rf5_client_lab import client
from rf5_lab import operate


def check(ok, reason):
    if not ok:
        raise AssertionError(reason)


def failure(chip, cmd, file, message):
    before = chip.read_bytes()
    try:
        client(chip, cmd, file)
    except RuntimeError as e:
        check(message in str(e), str(e))
    else:
        raise AssertionError('unexpected success: ' + cmd)
    check(chip.read_bytes() == before, 'chip modified after failing preflight')


def configuration_hashes(trace):
    # Decode physical backend operations rather than hashing client buffers.
    hashes = []
    bits = []
    recent = []
    with trace.open() as stream:
        for line in stream:
            recent = (recent + [line.strip()])[-4:]
            if recent == ['WD 02', 'WD 06', 'WC 00', 'WC 04']:
                bits.append(0)
            elif recent == ['WD 03', 'WD 07', 'WC 00', 'WC 04']:
                bits.append(1)
            elif line.startswith('RC ') and bits:
                check(len(bits) == 22224, 'incomplete configuration burst')
                data = bytes(sum(v << k for k, v in enumerate(bits[i:i+8]))
                             for i in range(0, len(bits), 8))
                hashes.append(hashlib.sha256(data).hexdigest())
                bits = []
    return hashes


def main(core=None):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chip, src, out = (root / n for n in ('chip', 'input', 'output'))
        blank = b'\xff' * 2048
        a = random.Random(1715).randbytes(2048)
        b = random.Random(2716).randbytes(2048)
        chip.write_bytes(blank)
        src.write_bytes(a)
        if core:
            lib, = [p for p in core.iterdir() if p.name.lower() == 'picprog.lib']
            trace = root / 'private.trace'
            client(chip, 'WRF5', src, lib, trace)
            check(configuration_hashes(trace) == [
                '7c382f7d667e53e06ce0f64ab70afeb2a6277c2c2b38e20a73b0c1d5679858be',
                'ad7ce1115d330be3728c8a4d4b69d197dbdb5dabc7eb4660dc33cb4354fc613e'],
                'configuration differs from vendor trace')
        else:
            client(chip, 'WRF5', src)
        check(chip.read_bytes() == a, 'program differs from input')
        client(chip, 'VRF5', src)
        client(chip, 'RRF5', out)
        check(out.read_bytes() == a, 'independent readback mismatch')
        out.unlink()
        if core:
            operate(core, chip, 'read', out)
            check(out.read_bytes() == a, 'vendor read of independent write differs')
            out.unlink()
        chip.write_bytes(blank)
        src.write_bytes(b)
        if core:
            operate(core, chip, 'write', src)
        else:
            chip.write_bytes(b)
        client(chip, 'RRF5', out)
        check(out.read_bytes() == b, 'independent read of second image differs')
        # One clear at the start would succeed; the forbidden change at the last
        # byte must prevent *both* writes.
        target = bytearray(b)
        target[0] = 0
        target[-1] = 255
        check(b[-1] != 255 and b[0] != 0, 'bad negative fixture')
        src.write_bytes(target)
        failure(chip, 'WRF5', src, 'Requires erase at 07ff')
        failure(chip, 'VRF5', src, 'Verify mismatch')
        target[-1] = b[-1]
        src.write_bytes(target)
        client(chip, 'WRF5', src)
        check(chip.read_bytes() == target, 'additional clear failed')
        for size in [2047, 2049]:
            src.write_bytes(bytes(size))
            failure(chip, 'WRF5', src, 'Expected exactly 2048')
        print('PASS: independent DOS read/write/verify and failure checks' +
              ('; original software cross-read in both directions' if core else ''))


if __name__ == '__main__':
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
