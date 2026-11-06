#!/usr/bin/env python3
"""Run two independent DOS clients against an explicitly selected AT28C16."""
# SPDX-License-Identifier: GPL-2.0-only
from concurrent.futures import ProcessPoolExecutor
from itertools import zip_longest
from pathlib import Path
import os
import runpy
import sys
import tempfile

m=runpy.run_path(str(Path(__file__).with_name('lpt-parity.py')))
PROFILE='AT28C16,P'


def checked_trace(gold, actual, timeout):
    a,b=gold.read_bytes(),actual.read_bytes()
    if timeout:
        # A timer-bound poll loop cannot have a fixed iteration count on
        # different DOS binaries. Only remove complete, identical busy reads.
        # Address 17, target 00: busy D7=1, other bits=17 in never-ready mode
        # (remaining starts at zero). Both sides must exit the loop and park.
        import re
        pattern=rb'(?:WD 08\nRS [0-9a-f]8\nWD 09\nRS [89a-f]8\n){32,}'
        spans=[]
        for raw in (a,b):
            hits=list(re.finditer(pattern,raw))
            assert len(hits)==1, 'missing sustained busy polls'
            h=hits[0]; loop=h.group()
            assert loop == loop[:24]*(len(loop)//24)
            assert b'WD 85\n' in raw[h.end():], 'no shutdown after timeout'
            spans.append((raw[:h.start()],loop[:24],raw[h.end():]))
        assert spans[0]==spans[1], 'timeout entry, busy sample or shutdown differs'
    elif a!=b:
        for i,(x,y) in enumerate(zip_longest(a.splitlines(),b.splitlines()),1):
            if x!=y: raise AssertionError(f'event {i}: reference {x!r}, client {y!r}')
    return a.count(b'\n'), b.count(b'\n')


def scenario(spec):
    core,op,start,data,initial,busy,outcome=spec
    os.environ['PP_EEPROM_BUSY']=busy
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);chip=d/'chip';file=d/'target'
        expected=bytearray(initial)
        if outcome=='ok' and op in ('WRITE','OVERWRITE'): expected[start:start+len(data)]=data
        for ref in (True,False):
            chip.write_bytes(initial)
            file.unlink(missing_ok=True)
            if op not in ('READ','CHECK'): file.write_bytes(data)
            if ref:
                m['reference'](core,chip,op,start,len(data),file,d/'gold',
                               failure=outcome!='ok',profile=PROFILE)
            else:
                lib,=(p for p in core.iterdir() if p.name.lower()=='picprog.lib')
                try: m['client'](chip,op,file,lib,d/'ours',start,len(data),PROFILE)
                except RuntimeError as ex:
                    if outcome=='ok' or f'at {start:04x}' not in str(ex).lower(): raise
                else:
                    if outcome!='ok': raise AssertionError('expected failure')
            assert chip.read_bytes()==expected,(op,start,busy,'chip mismatch')
            if op=='READ': assert file.read_bytes()==data
        n,k=checked_trace(d/'gold',d/'ours',busy=='never')
        return f'{op} at {start:04X}, length {len(data)}, busy={busy}, {outcome}: {n}/{k} events'


def cross(core):
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);chip=d/'chip';f=d/'file';chip.write_bytes(b'\xff'*2048)
        lib,=(p for p in core.iterdir() if p.name.lower()=='picprog.lib')
        f.write_bytes(b'\0')
        m['reference'](core,chip,'WRITE',0,1,f,d/'w',profile=PROFILE)
        f.unlink();m['client'](chip,'READ',f,lib,None,0,1,PROFILE);assert f.read_bytes()==b'\0'
        f.write_bytes(b'\xff');m['client'](chip,'WRITE',f,lib,None,0,1,PROFILE)
        f.unlink();m['reference'](core,chip,'READ',0,1,f,d/'r',profile=PROFILE)
        assert f.read_bytes()==b'\xff' and chip.read_bytes()==b'\xff'*2048


if __name__=='__main__':
    core=Path(sys.argv[1]); blank=b'\xff'*2048; zero=bytes(2048)
    pattern=bytes((i*13+9)&255 for i in range(257))
    specs=[('WRITE',0,b'\0',blank,'0','ok'),('WRITE',2047,b'\xff',zero,'3','ok'),
           ('WRITE',255,pattern,zero,'2','ok'),('READ',0,blank,blank,'0','ok'),
           ('CHECK',0,blank,blank,'0','ok'),('VERIFY',0,zero,zero,'0','ok'),
           ('OVERWRITE',255,pattern,blank,'3','ok'),('OVERWRITE',17,b'\xff',zero,'0','reject'),
           ('CHECK',17,b'\xff',zero,'0','reject'),('VERIFY',17,b'\xff',zero,'0','reject'),
           ('WRITE',17,b'\0',blank,'never','timeout')]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for msg in pool.map(scenario,[(core,*s) for s in specs]): print(msg,flush=True)
    cross(core)
    print('PASS: original and independent client cross-read both byte transitions')
