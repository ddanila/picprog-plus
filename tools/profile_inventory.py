#!/usr/bin/env python3
"""Inventory device/algorithm labels in the user's reference executable."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
from collections import Counter
import hashlib
from pathlib import Path


def catalog(exe):
    data = exe.read_bytes()
    if hashlib.sha256(data).hexdigest() != '3959f7375a9a871364864674ea4a65799da5f81b51294fe98a6e8d52a028183a':
        raise ValueError('expected the identified Phyton 2.77 DOS executable')
    fields = data[0x451e2:0x4804b].decode('ascii').split('\0')
    if fields.pop() or len(fields) % 3:
        raise ValueError('incomplete device table')
    return list(zip(fields[::3], fields[1::3], fields[2::3]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('--list', action='store_true', help='print manufacturer, device and algorithm for each entry')
    args = parser.parse_args()
    rows = catalog(args.exe)
    if args.list:
        for row in rows: print(*row, sep='\t')
    else:
        for name, count in Counter(r[2] for r in rows).most_common(): print(f'{name}: {count}')
        print(f'Total: {len(rows)} entries')
