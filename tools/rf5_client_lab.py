#!/usr/bin/env python3
"""Run the independent DOS client against the file-backed PicProg. No Phyton files."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
from pathlib import Path
import shutil
import tempfile

from rf5_lab import run_guest


def client(chip, command, image, library=None, trace=None, start=0, length=2048):
    com = Path(__file__).resolve().parents[1] / 'build/dos/PICRF5.COM'
    if chip.is_symlink() or not chip.is_file() or chip.stat().st_size != 2048:
        raise ValueError('expected a regular 2048-byte chip image')
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
        if (start,length) != (0,2048):
            arg += f' {start} {length}'
        (drive / 'RUN.BAT').write_bytes(
            (f'@echo off\r\nPICRF5.COM {command} IMAGE.BIN 378{arg} > RESULT.TXT\r\n'
             'if errorlevel 1 goto end\r\necho ok > PASS.OK\r\n:end\r\n').encode())
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
    args = parser.parse_args()
    print(client(args.chip, args.command, args.image, args.library, start=args.start, length=args.length))
