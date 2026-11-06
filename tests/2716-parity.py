#!/usr/bin/env python3
"""Compare native selection and implicit-default operations on a 2 KiB image."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import random
import runpy
import shutil
import subprocess
import tempfile

common = runpy.run_path(str(Path(__file__).with_name('lpt-parity.py')))
from rf5_client_lab import client
from rf5_lab import run_guest


def rejected(core, profile, data, start=0, length=2048):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        d = root/'drive'
        d.mkdir()
        files = {p.name.lower(): p for p in core.iterdir()}
        for ext in ('exe','ovl','cfg','lib'):
            p = files['picprog.'+ext]
            shutil.copyfile(p,d/p.name.upper())
        chip = root/'chip'
        chip.write_bytes(data)
        # If selection unexpectedly succeeds, READ is nondestructive and its
        # output proves whether execution got past SET_ROM_TYPE.
        select = '' if profile == 'DEFAULT' else f'SET_ROM_TYPE({profile})\r\n'
        batch = f'MESSAGE ON\r\n{select}READ(0,{length-1},{start},0)\r\nSAVE("DUMP.BIN",BIN,0,0,2047)\r\nPRINT "DONE"\r\nEND\r\n'
        (d/'TASK.B').write_bytes(batch.encode('cp866'))
        try:
            run_guest(root,d,chip,['PICPROG.EXE /LPT1 TASK.B > OUT.TXT'],timeout=20,trace=root/'gold')
        except subprocess.TimeoutExpired:
            if profile.isascii(): raise
            result = 'did not return within 20 s'
        else:
            report = (d/'OUT.TXT').read_text(encoding='cp866')
            if 'ERROR in line 2:' not in report or 'DONE' in report: raise AssertionError(report)
            result = report.split('ERROR in line 2:')[1].splitlines()[0].strip()
            expected = 'Адреса PROM' if profile=='DEFAULT' else 'Неверный тип ПЗУ'
            if expected not in result: raise AssertionError(report)
        if (d/'DUMP.BIN').exists() or chip.read_bytes()!=data: raise AssertionError(profile)
        try: client(chip,'READ',root/'dump',files['picprog.lib'],root/'ours',start,length,profile)
        except RuntimeError as err:
            expected = 'outside default range' if profile=='DEFAULT' else 'Invalid ROM type'
            if expected not in str(err): raise
        else: raise AssertionError('unexpected selection success')
        gold = (root/'gold').read_bytes()
        if gold != (root/'ours').read_bytes() or chip.read_bytes()!=data or (root/'dump').exists():
            raise AssertionError(f'{profile}: trace, image or output mismatch')
        return f'{profile}: {len(gold.splitlines())} identical events; original: {result}'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('core',type=Path)
    p.add_argument('--image',type=Path,help='optional 2048-byte dump; input is never modified')
    args = p.parse_args()
    image = args.image.read_bytes() if args.image else random.Random(2716).randbytes(2048)
    if len(image)!=2048: p.error('expected a 2048-byte image')
    print('Fixture SHA-256:', hashlib.sha256(image).hexdigest(),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for s in pool.map(lambda op: common['case'](args.core,op,0,2048,2716,
                profile='DEFAULT',payload=image), ('READ','VERIFY','CHECK','WRITE','OVERWRITE')):
            print('Default:',s,flush=True)
        print('Implicit READ():',common['case'](args.core,'READ',0,2048,2716,
                profile='DEFAULT',payload=image,omit_range=True),flush=True)
        # An 8 KiB backing chip rules out the adapter as the cause of rejection.
        print('Default range:',rejected(args.core,'DEFAULT',image*4,2046,5),flush=True)
        for s in pool.map(lambda name: rejected(args.core,name,image), ('2716,I','2716,Q','U2716C35,I',
                'K573RF2,I','K573RF5,I','К573РФ2,I','К573РФ5,I','РФ2,I','РФ5,I')):
            print(s,flush=True)
