#!/usr/bin/env python3
"""Compare every ppdev event from original PicProg 2.77 and independent PICRF5."""
# SPDX-License-Identifier: GPL-2.0-only
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from itertools import zip_longest
import os
from pathlib import Path
import random
import shutil
import sys
import subprocess
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rf5_client_lab import client
from rf5_lab import run_guest


def reference(core, chip, op, start, length, file, trace, failure=False, profile='27C64,Q', omit_range=False):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        d = root / 'drive'
        d.mkdir()
        for name in ('picprog.exe', 'picprog.ovl', 'picprog.lib', 'picprog.cfg'):
            src, = (p for p in core.iterdir() if p.name.lower() == name)
            shutil.copyfile(src, d / name.upper())
        batch = ['MESSAGE ON']
        if profile != 'DEFAULT': batch.append(f'SET_ROM_TYPE({profile})')
        if op in ('VERIFY', 'WRITE', 'OVERWRITE'):
            shutil.copyfile(file, d / 'IMAGE.BIN')
            batch.append('LOAD("IMAGE.BIN",BIN)')
        args = f'{start},{start+length-1}' if op == 'CHECK' else f'0,{length-1},{start},0'
        batch.append(f'{op}({args if not omit_range else ""})')
        if op == 'READ':
            batch.append(f'SAVE("IMAGE.BIN",BIN,0,0,{length-1})')
        batch += ['PRINT "PARITY-COMPLETE"', 'END']
        (d / 'TASK.B').write_bytes(('\r\n'.join(batch)+'\r\n').encode())
        try:
            run_guest(root, d, chip, ['PICPROG.EXE /LPT1 TASK.B > REPORT.TXT'],
                      timeout=18 if failure else 180, trace=trace, socket="AT28C16" if profile=="AT28C16,P" else None)
        except subprocess.TimeoutExpired:
            # 2.77 blocks for operator input on batch chip errors. Only compare
            # the bus observations, not what a later keypress would do.
            if not failure: raise
        if failure:
            if 'PARITY-COMPLETE' in (d/'REPORT.TXT').read_text(encoding='cp866'):
                raise AssertionError('unexpected reference success')
            return
        report = (d / 'REPORT.TXT').read_text(encoding='cp866')
        if 'PARITY-COMPLETE' not in report or 'ERROR' in report.upper():
            raise AssertionError(report)
        if op == 'READ':
            file.write_bytes((d / 'IMAGE.BIN').read_bytes())


def case(core, op, start, length, seed, capacity=2048, profile='27C64,Q', payload=None, omit_range=False):
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        chip, file = d/'chip', d/'file'
        blank = b'\xff'*capacity
        before = blank if op in ('WRITE','CHECK') else random.Random(seed).randbytes(capacity)
        if op == 'OVERWRITE' and length % 256:
            # Original treats the tail of a 256-byte block as erased data.
            end = start + length
            pad = min(capacity-end, 256-length%256)
            before = before[:end] + b'\xff'*pad + before[end+pad:]
        segment = before[start:start+length]
        target = (random.Random(seed+1).randbytes(length) if op == 'WRITE'
                  else bytes(x & 0x55 for x in segment) if op == 'OVERWRITE' else segment)
        if payload is not None:
            if start or length != capacity or len(payload) != capacity:
                raise ValueError('payload must cover the entire chip')
            if op in ('VERIFY','READ'): before = target = segment = payload
            if op == 'WRITE': target = payload
            if op == 'OVERWRITE':
                before = bytes(x | 0x55 for x in payload)
                target = payload
        expected = before[:start] + target + before[start+length:]
        for i, trace in enumerate((d/'original', d/'ours')):
            chip.write_bytes(before)
            if file.exists(): file.unlink()
            if op not in ('READ','CHECK'): file.write_bytes(target)
            if not i:
                reference(core,chip,op,start,length,file,trace,profile=profile,omit_range=omit_range)
            else:
                lib, = (p for p in core.iterdir() if p.name.lower() == 'picprog.lib')
                client(chip,op,file,lib,trace,start,length,profile)
            if chip.read_bytes()!=expected or (op=='READ' and file.read_bytes()!=segment):
                raise AssertionError(f'{op} content mismatch')
        with (d/'original').open('rb') as gold, (d/'ours').open('rb') as actual:
            for n,(x,y) in enumerate(zip_longest(gold,actual),1):
                if x!=y:
                    raise AssertionError(f'{op} {start}:{length} event {n}: {x!r} != {y!r}')
        return f'{op} {start:04x}..{start+length-1:04x}: {n} identical events'


def negative(core, op, skip=0, padding=False):
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        original = bytearray(b'\xff'*2048)
        if op == 'CHECK': original[17] = 0x7e
        if op == 'OVERWRITE': original[17] = 0
        start, length = (17,3) if op == 'WRITE' else (0,256)
        if padding:
            start, length = 253, 263
            original[start+length+3] = 0
            skip = length
        chip, file = d/'chip', d/'input'
        file.write_bytes(b'\xff'*skip + b'\x7f'*(length-skip))
        chip.write_bytes(original)
        reference(core,chip,op,start,length,file,d/'gold',failure=True)
        if chip.read_bytes()!=original: raise AssertionError('unexpected reference write')
        lib, = (p for p in core.iterdir() if p.name.lower() == 'picprog.lib')
        try: client(chip,op,file,lib,d/'actual',start,length)
        except RuntimeError as error:
            if ' at ' not in str(error): raise
        else: raise AssertionError('client should have failed')
        if chip.read_bytes()!=original or (d/'gold').read_bytes()!=(d/'actual').read_bytes():
            raise AssertionError(f'{op} fault trace or chip mismatch')
        return f'{op} failure: identical bus events up to original operator prompt'


def startup_failure(spec):
    core, key, value = spec
    os.environ[key] = value
    try:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            chip, file = d/'chip', d/'input'
            chip.write_bytes(b'\xff'*2048)
            reference(core,chip,'CHECK',0,1,file,d/'gold',failure=True)
            lib, = (p for p in core.iterdir() if p.name.lower()=='picprog.lib')
            try: client(chip,'CHECK',file,lib,d/'actual',0,1)
            except RuntimeError as error:
                if 'Configuration, ID or socket check failed' not in str(error): raise
            else: raise AssertionError('unexpected startup success')
            if (d/'actual').read_bytes() != (d/'gold').read_bytes():
                raise AssertionError(f'{key}={value} startup trace mismatch')
            return f'{key}={value}: identical startup failure trace'
    finally:
        del os.environ[key]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('core',type=Path)
    parser.add_argument('--seed',type=int,default=1715)
    parser.add_argument('--faults',action='store_true',help='also compare bounded reference error paths')
    args=parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda spec: case(args.core,*spec,args.seed),
                               [(op,s,n) for s,n in [(0,2048),(253,263)]
                                for op in ('READ','CHECK','VERIFY','WRITE','OVERWRITE')]):
            print(result,flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda op: case(args.core,op,0,8192,args.seed,8192),
                               ('READ','WRITE','CHECK','VERIFY','OVERWRITE')):
            print(result,flush=True)
    if args.faults:
        with ThreadPoolExecutor(max_workers=3) as pool:
            for result in pool.map(lambda op: negative(args.core,op), ('CHECK','VERIFY','OVERWRITE')):
                print(result,flush=True)
    specs = [(p,op,start,length,capacity)
             for p,start,length,capacity in [('27C64,I',4094,9,8192),
                                             ('27C64,I',0,8192,8192),
                                             ('27C128,Q',8190,263,16384),
                                             ('27C128,I',8190,263,16384)]
             for op in ('READ','CHECK','VERIFY','WRITE','OVERWRITE')]
    def profile_case(spec):
        profile, op, start, length, capacity = spec
        return profile + ': ' + case(args.core,op,start,length,args.seed,capacity,profile)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(profile_case,specs): print(result,flush=True)
    if args.faults:
        with ProcessPoolExecutor(max_workers=3) as pool:
            for result in pool.map(startup_failure, [(args.core,'PP_LAB_MAP','06:00,05:00,0f:00,0c:70'),
                    (args.core,'PP_LAB_MAP','06:f0,05:00,0f:00,0c:00'), (args.core,'PP_LAB_ECHO','0'),
                    (args.core,'PP_EMPTY_SOCKET','1')]):
                print(result,flush=True)
        os.environ['PP_PULSE_FAULT']='1'
        try: print('pulse status fault:',negative(args.core,'WRITE',2))
        finally: del os.environ['PP_PULSE_FAULT']
        print('dirty padding:', negative(args.core,'WRITE',padding=True))
    print('crosses socket boundary:',case(args.core,'WRITE',1775,273,args.seed))
    os.environ['PP_DROP_PULSES']='2'
    print('retry:',case(args.core,'WRITE',17,3,args.seed))
    print('Intelligent retry:',case(args.core,'WRITE',4094,5,args.seed,8192,'27C64,I'))
    if args.faults:
        os.environ['PP_DROP_PULSES']='30'
        with ThreadPoolExecutor(max_workers=2) as pool:
            for skip, result in zip((0, 2), pool.map(lambda k: negative(args.core,'WRITE',k), (0, 2))):
                print(f'after {skip} unchanged bytes:', result)
