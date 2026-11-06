#!/usr/bin/env python3
"""Opt-in integration test; needs a private extracted copy of PicProg 2.77."""
# SPDX-License-Identifier: GPL-2.0-only
import hashlib
from pathlib import Path
import random
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rf5_lab import operate


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def main(core):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        chip, src, out = (root / n for n in ('chip', 'src', 'out'))
        # Start with a populated chip before any programming to catch a read
        # implementation that relies on caching the last write.
        seed = random.Random(573).randbytes(2048)
        chip.write_bytes(seed)
        operate(core, chip, 'read', out)
        require(out.read_bytes() == seed, 'preloaded chip read mismatch')
        out.unlink()
        chip.write_bytes(b'\xff' * 2048)
        payload = random.Random(1715).randbytes(2048)
        src.write_bytes(payload)
        print(operate(core, chip, 'write', src))
        print(operate(core, chip, 'read', out))
        require(chip.read_bytes() == out.read_bytes() == payload, 'full image mismatch')
        print('Full write and fresh-session read:', hashlib.sha256(payload).hexdigest())
        cut = bytes(v & 0x55 for v in payload[254:259])
        src.write_bytes(cut)
        operate(core, chip, 'write', src, 254)
        out.unlink()
        operate(core, chip, 'read', out, 253, 7)
        require(out.read_bytes() == payload[253:254]+cut+payload[259:260], 'partial read mismatch')
        final = chip.read_bytes()
        for where, data in ((254, b'\xff' * 5), (2047, b'\x00\x00')):
            src.write_bytes(data)
            try:
                operate(core, chip, 'write', src, where)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid write was accepted')
            require(chip.read_bytes() == final, 'rejected write changed chip')


if __name__ == '__main__':
    main(Path(sys.argv[1]))
