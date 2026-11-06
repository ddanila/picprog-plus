#!/usr/bin/env python3
"""Run the independent DOS client against the file-backed PicProg. No Phyton files."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
from pathlib import Path
import shutil
import tempfile

from rf5_lab import run_guest


# Negative selections are intentional: let the guest produce the reference
# startup traffic and reject them, never substitute a programming algorithm.
REJECTED_2716 = tuple(name + ',' + mode
    for name in ('2716','U2716C35','RF2','RF5','K573RF2','K573RF5','К573РФ2','К573РФ5','РФ2','РФ5')
    for mode in ('I','Q'))
PROFILES = ('27C64,Q','27C64,I','27C128,Q','27C128,I','DEFAULT') + REJECTED_2716


def client(chip, command, image, library=None, trace=None, start=0, length=2048, profile='27C64,Q'):
    com = Path(__file__).resolve().parents[1] / 'build/dos/PICRF5.COM'
    if chip.is_symlink() or not chip.is_file() or chip.stat().st_size not in (2048,8192,16384):
        raise ValueError('expected a regular 2048-, 8192- or 16384-byte chip image')
    if length < 1 or start < 0 or start + length > chip.stat().st_size:
        raise ValueError('request outside selected chip')
    if command not in ('RRF5', 'VRF5', 'WRF5', 'READ', 'VERIFY', 'WRITE', 'OVERWRITE', 'CHECK'):
        raise ValueError('unknown command')
    if command in ('RRF5','READ') and (image.exists() or image.is_symlink()):
        raise ValueError('read destination already exists')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        drive = root / 'drive'
        drive.mkdir()
        shutil.copyfile(com, drive / 'PICRF5.COM')
        transfer = drive / 'IMAGE.BIN'
        if command not in ('RRF5','READ','CHECK'):
            shutil.copyfile(image, transfer)
        arg = ''
        if library is not None:
            shutil.copyfile(library, drive / 'PICPROG.LIB')
            arg = ' PICPROG.LIB'
        if profile not in PROFILES:
            raise ValueError('unknown profile')
        if (start,length) != (0,2048) or profile != '27C64,Q':
            arg += f' {start} {length}'
        if profile != '27C64,Q':
            arg += ' ' + profile
        (drive / 'RUN.BAT').write_bytes(
            (f'@echo off\r\nPICRF5.COM {command} IMAGE.BIN 378{arg} > RESULT.TXT\r\n'
             'if errorlevel 1 goto end\r\necho ok > PASS.OK\r\n:end\r\n').encode('cp866'))
        run_guest(root, drive, chip, ['call RUN.BAT'], trace=trace)
        msg = (drive / 'RESULT.TXT').read_text(encoding='cp866')
        if not (drive / 'PASS.OK').exists() or f'{command} OK: {length} bytes' not in msg:
            raise RuntimeError(msg.strip() or 'DOS client failed')
        if command in ('RRF5','READ'):
            data = transfer.read_bytes()
            if len(data) != length:
                raise RuntimeError('incomplete DOS read')
            with image.open('xb') as f:
                f.write(data)
        return msg.strip()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('chip', type=Path)
    parser.add_argument('command', choices=['RRF5', 'WRF5', 'VRF5', 'READ','VERIFY','WRITE','OVERWRITE','CHECK'])
    parser.add_argument('image', type=Path)
    parser.add_argument('--library', type=Path, help='optional local Phyton configuration library')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--length', type=int, default=2048)
    parser.add_argument('--profile', choices=PROFILES, default='27C64,Q')
    args = parser.parse_args()
    print(client(args.chip, args.command, args.image, args.library, start=args.start, length=args.length, profile=args.profile))
