#!/usr/bin/env python3
"""Run a private copy of PicProg against a synthetic LPT port on Linux."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(core, trace, status, mapping, seconds, help_only):
    lib = Path(__file__).resolve().parents[1] / 'build/virtual_ppdev.so'
    if not lib.is_file():
        raise SystemExit('run make lab first')
    if not any(p.name.lower() == 'picprog.exe' for p in core.iterdir()):
        raise SystemExit('expected extracted DOS Core directory')
    trace = trace.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        drive = root / 'drive'
        shutil.copytree(core, drive)
        (drive / 'LABREAD.B').write_bytes(b'MESSAGE ON\r\nREAD(0,0,0,0)\r\nEND\r\n')
        endpoint = root / 'endpoint'
        endpoint.touch()
        # A nonprivileged copy: distro builds can have capabilities that disable LD_PRELOAD.
        box = root / 'dosbox-x'
        shutil.copy(shutil.which('dosbox-x') or '/usr/bin/dosbox-x', box)
        env = dict(os.environ, PP_ENDPOINT=str(endpoint), PP_TRACE=str(trace),
                   PP_STATUS=hex(status), PP_MAP=mapping, LD_PRELOAD=str(lib),
                   SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        cmd = [str(box), '-silent', '-fastlaunch']
        for setting in ('dosbox machine=cga', 'dosbox allow more than 640kb base memory=true',
                        'cpu cycles=20000', f'parallel parallel1=reallpt realport:{endpoint}',
                        'parallel parallel2=disabled', 'parallel parallel3=disabled'):
            cmd.extend(['-set', setting])
        for step in (f'mount c {drive}', 'c:', 'picprog.exe ' +
                     ('/H' if help_only else '/LPT1 LABREAD.B'), 'exit'):
            cmd.extend(['-c', step])
        with (root / 'emulator.log').open('wb') as log:
            try:
                p = subprocess.run(cmd, cwd=root, env=env, timeout=seconds, stdout=log,
                                   stderr=subprocess.STDOUT)
                if p.returncode:
                    raise SystemExit(f'DOSBox-X exited with {p.returncode}')
            except subprocess.TimeoutExpired:
                print('Stopped at observation deadline; guest completion not established.')
        lines = trace.read_text().splitlines()
        if not lines or any(x.startswith('UNKNOWN') for x in lines):
            raise SystemExit('empty trace or unhandled ioctl')
        from collections import Counter
        print(len(lines), 'events;', dict(Counter(x.split()[0] for x in lines)))
        selected = None
        polls = Counter()
        for line in lines:
            if line.startswith('WD '):
                selected = line[3:]
            if line.startswith('RS '):
                polls[selected, line[3:]] += 1
        print('status reads (last data, reply):', dict(polls))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('core', type=Path)
    p.add_argument('trace', type=Path, help='new private output file')
    p.add_argument('--status', type=lambda v: int(v, 0), default=0xd8)
    p.add_argument('--map', default='', help='hex last-data:status pairs; use slash for a cyclic sequence')
    p.add_argument('--seconds', type=int, default=8)
    p.add_argument('--help-only', action='store_true', help='vendor usage screen as baseline')
    args = p.parse_args()
    if args.trace.exists() or not 0 <= args.status <= 255 or args.seconds < 1:
        p.error('use a new trace path, byte status and positive duration')
    run(args.core, args.trace, args.status, args.map, args.seconds, args.help_only)
