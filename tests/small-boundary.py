#!/usr/bin/env python3
"""Compare the default profile at the physical boundary and at a defective cell."""
# SPDX-License-Identifier: GPL-2.0-only
from concurrent.futures import ProcessPoolExecutor
from itertools import zip_longest
from pathlib import Path
import os
import runpy
import sys
import tempfile

m = runpy.run_path(str(Path(__file__).with_name('lpt-parity.py')))


def pulses(path):
    """Qualified programming edges on the programmer address bus (before aliasing)."""
    reg=[0]*16; last=None; bus=0; result=[]
    for line in path.read_text().splitlines():
        event,value=line.split(); value=int(value,16)
        if event=='WD': bus=value
        if event!='WC': continue
        if value==5 and last!=5:
            index=bus&15; nibble=bus>>4
            if index==14 and reg[14]==8 and nibble==12 and reg[6]==2 and reg[7]==4:
                result.append(reg[2] | reg[3]<<4 | reg[13]<<8)
            reg[index]=nibble
        last=value
    return result


def compare(spec):
    core, op, count, capacity, fault = spec
    start = 2048-count
    initial = bytearray([255])*capacity
    if fault == 'dirty': initial[0] = 0x5a
    data = bytes([0x50])*count
    expected = initial.copy()
    expected[start:2048] = data
    bad = None
    if fault == 'stuck':
        bad = start+3
        os.environ['PP_STUCK_CELL'] = f'{bad:x}:01'
        expected[bad] |= 1
        expected[bad+1:] = initial[bad+1:]
    if fault == 'retry': os.environ['PP_DROP_PULSES']='1'
    if fault == 'dirty' and capacity==2048: bad = 2048
    try:
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); chip=d/'chip'; f=d/'payload'; f.write_bytes(data)
            for reference in (True,False):
                chip.write_bytes(initial)
                if reference:
                    m['reference'](core,chip,op,start,count,f,d/'gold',failure=bad is not None,profile='DEFAULT')
                else:
                    lib, = (p for p in core.iterdir() if p.name.lower()=='picprog.lib')
                    try: m['client'](chip,op,f,lib,d/'ours',start,count,'DEFAULT')
                    except RuntimeError as e:
                        if bad is None or f'at {bad:04x}' not in str(e).lower(): raise
                    else:
                        if bad is not None: raise AssertionError('unexpected completion')
                if chip.read_bytes()!=expected:
                    addr=next(i for i,(x,y) in enumerate(zip(chip.read_bytes(),expected)) if x!=y)
                    raise AssertionError(f'{spec}: unexpected cell at {addr:04x}, reference={reference}')
            with (d/'gold').open('rb') as a,(d/'ours').open('rb') as b:
                for n,(x,y) in enumerate(zip_longest(a,b),1):
                    if x!=y: raise AssertionError(f'{spec}, event {n}: {x!r} != {y!r}')
            attempts=pulses(d/'gold')
            if bad is not None: assert attempts.count(bad)==25
            if fault=='retry': assert attempts.count(start)==2
            if bad==2048: assert attempts[-1]==2048
            return f'{op} {start:04X}..07FF {capacity} {fault}: {n} identical events'
    finally:
        for k in ('PP_STUCK_CELL','PP_DROP_PULSES'): os.environ.pop(k,None)


if __name__ == '__main__':
    core=Path(sys.argv[1])
    specs=[(core,op,n,2048,'normal') for op in ('WRITE','OVERWRITE') for n in (1,256,257)]
    specs += [(core,op,257,cap,'dirty') for op in ('WRITE','OVERWRITE') for cap in (2048,8192)]
    specs += [(core,'WRITE',8,2048,f) for f in ('stuck','retry')]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(compare,specs): print(result,flush=True)
