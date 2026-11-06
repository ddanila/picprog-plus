#!/usr/bin/env python3
"""Read or program a virtual 2 KiB К573РФ5 via the original DOS application."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run_guest(root, drive, backing, commands, timeout=180, trace=None):
    ep = root / 'port'
    ep.touch()
    box = root / 'dosbox-x'
    shutil.copy(shutil.which('dosbox-x') or '/usr/bin/dosbox-x', box)
    lib = Path(__file__).resolve().parents[1] / 'build/virtual_ppdev.so'
    if not lib.is_file():
        raise ValueError('run make lab first')
    env = dict(os.environ, LD_PRELOAD=str(lib), PP_ENDPOINT=str(ep), PP_TRACE=str(trace.resolve()) if trace is not None else os.devnull,
               PP_RF5_IMAGE=str(backing.resolve()), PP_ECHO_DE='1', PP_STATUS='0xd8',
               PP_MAP='06:f0,05:00,0f:00,0c:70', SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    cmd = [str(box), '-silent', '-fastlaunch']
    for option in ('dosbox machine=cga', 'dosbox allow more than 640kb base memory=true',
                   'cpu cycles=60000', f'parallel parallel1=reallpt realport:{ep}',
                   'parallel parallel2=disabled', 'parallel parallel3=disabled'):
        cmd += ['-set', option]
    for step in (f'mount c {drive}', 'c:', *commands, 'exit'):
        cmd += ['-c', step]
    subprocess.run(cmd, cwd=root, env=env, timeout=timeout, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def operate(core, backing, operation, file, start=0, size=None, timeout=180):
    if not backing.is_file() or backing.is_symlink() or backing.stat().st_size != 2048:
        raise ValueError('chip must be a regular, exactly 2048-byte image')
    expected = None
    if operation == 'write':
        expected = file.read_bytes()
        size = len(expected)
    elif file.exists() or file.is_symlink():
        raise ValueError('read destination already exists')
    elif size is None:
        size = 2048 - start
    if size < 1 or start < 0 or start + size > 2048:
        raise ValueError('range outside 0000..07FF')
    before = backing.read_bytes()
    if expected is not None and any((o & n) != n for o, n in zip(before[start:], expected)):
        raise ValueError('requested 0-to-1 transition requires an erased chip')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        drive = root / 'drive'
        drive.mkdir()
        for name in ('picprog.exe', 'picprog.ovl', 'picprog.lib', 'picprog.cfg'):
            src, = (p for p in core.iterdir() if p.name.lower() == name)
            shutil.copyfile(src, drive / name.upper())
        params = f'0,{size-1},{start},0'
        if expected is not None:
            (drive / 'INPUT.BIN').write_bytes(expected)
            command = 'WRITE' if before[start:start+size] == b'\xff' * size else 'OVERWRITE'
            batch = ['LOAD("INPUT.BIN",BIN)', f'{command}({params})']
        else:
            batch = [f'READ({params})', f'SAVE("OUTPUT.BIN",BIN,0,0,{size-1})']
        batch.insert(0, 'SET_ROM_TYPE(27C64,Q)')
        batch += ['PRINT "RF5-LAB-COMPLETE"', 'END']
        (drive / 'LAB.B').write_bytes(('MESSAGE ON\r\n' + '\r\n'.join(batch) + '\r\n').encode())
        run_guest(root, drive, backing, ["PICPROG.EXE /LPT1 LAB.B > REPORT.TXT"], timeout)
        report = (drive / 'REPORT.TXT').read_text(encoding='cp866')
        if 'RF5-LAB-COMPLETE' not in report or 'ERROR' in report.upper():
            raise RuntimeError('DOS batch did not succeed: ' + report)
        if expected is None:
            raw = (drive / 'OUTPUT.BIN').read_bytes()
            if len(raw) != size or backing.read_bytes() != before:
                raise RuntimeError('incomplete or destructive read')
            with file.open('xb') as f:
                f.write(raw)
        elif backing.read_bytes() != before[:start] + expected + before[start + size:]:
            raise RuntimeError('chip content or surrounding addresses failed verification')
        return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('core', type=Path)
    p.add_argument('chip', type=Path)
    p.add_argument('operation', choices=('read', 'write'))
    p.add_argument('file', type=Path)
    p.add_argument('--start', type=lambda v: int(v, 0), default=0)
    p.add_argument('--size', type=lambda v: int(v, 0), help='length for read')
    p.add_argument('--timeout', type=int, default=180)
    a = p.parse_args()
    if a.operation == 'write' and a.size is not None:
        p.error('write length is the input file size')
    print(operate(a.core, a.chip, a.operation, a.file, a.start, a.size, a.timeout))
