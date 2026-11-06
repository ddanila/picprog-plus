#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
cd "$(dirname "$0")/.."
ravi=$(realpath "${DOSRAVI_DIR:-../dosravi}")
port=${DOSRAVI_TEST_PORT:-19572}
work=$(mktemp -d)
pid=
cleanup() {
  if [[ -n "$pid" ]]; then kill -KILL "$pid" 2>/dev/null || :; wait "$pid" || :; fi
  rm -rf "$work"
}
trap cleanup EXIT
make build/PPPORTS.COM
mkdir "$work/RAVI"
cp "$ravi/build/dos/DOSRAVI.COM" "$work/RAVI/"
box=$(command -v dosbox-x)
socket=
parallel=file
preload=
if [[ ${1:-} == --rf5 || ${1:-} == --at28c16 || ${1:-} == --reference ]]; then
  make dos lab
  preload="$PWD/build/virtual_ppdev.so"
  cp "$box" "$work/dosbox-x"
  box="$work/dosbox-x"
  touch "$work/endpoint"
  parallel="reallpt realport:$work/endpoint"
  python3 - "$work" <<'ENDPY'
import sys, random
from pathlib import Path
p = Path(sys.argv[1])
(p/'chip').write_bytes(b'\xff'*2048)
(p/'payload').write_bytes(random.Random(573).randbytes(2048))
ENDPY
fi
if [[ ${1:-} == --at28c16 ]]; then
  core=${2:?supply the extracted PicProg 2.77 Core directory}
  cp "$core/picprog.lib" "$work/RAVI/PICPROG.LIB"
  socket=AT28C16
fi
cpu=8086
machine=()
if [[ ${1:-} == --reference ]]; then
  core=${2:?supply the extracted PicProg 2.77 Core directory}
  for ext in exe ovl lib cfg; do
    cp "$core/picprog.$ext" "$work/RAVI/PICPROG.${ext^^}"
  done
  # Phyton 2.77 uses 186+ instructions and needs more DOS memory than PICRF5.
  cpu=386
  machine=(-set 'dosbox machine=cga' -set 'dosbox allow more than 640kb base memory=true')
  python3 - "$work" <<'ENDPY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
(p/'chip').write_bytes((p/'payload').read_bytes())
(p/'read.b').write_bytes(b'MESSAGE ON\r\nSET_ROM_TYPE(27C64,Q)\r\nREAD(0,2047,0,0)\r\nSAVE("DUMP.BIN",BIN,0,0,2047)\r\nEND\r\n')
ENDPY
fi
env PP_SOCKET="$socket" LD_PRELOAD="$preload" PP_ENDPOINT="$work/endpoint" PP_TRACE=/dev/null \
  PP_MAP=06:f0,05:00,0f:00,0c:70 PP_STATUS=0xd8 PP_ECHO_DE=1 PP_RF5_IMAGE="$work/chip" \
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$box" -silent -fastlaunch \
  -set 'sdl output=surface' "${machine[@]}" -set "cpu cputype=$cpu" -set 'cpu cycles=max' \
  -set "parallel parallel1=$parallel" \
  -set "serial serial1=nullmodem port:$port transparent:1 telnet:0 usedtr:0 rxdelay:0 txdelay:0" \
  -c "mount c $work" -c 'c:' -c 'cd RAVI' \
  -c 'echo ready > READY' -c 'DOSRAVI.COM /COM1 /BAUD:57600 /ROOT:C:\RAVI' >"$work/emulator.log" 2>&1 &
pid=$!
for _ in {1..100}; do [[ -f "$work/RAVI/READY" ]] && break; sleep .1; done
[[ -f "$work/RAVI/READY" ]] || { cat "$work/emulator.log"; exit 1; }
sleep 1  # allow the DOS agent to initialize its UART after the shell marker
ravi_run() {
  local sess=$1
  shift
  PYTHONPATH="$ravi" python3 -m dosravi.cli --tcp "127.0.0.1:$port" --baud 57600 \
    --session-dir "$work/$sess" run --note machine=DOSBox-X --note cable-adapter=nullmodem "$@"
}
if [[ ${1:-} == --reference ]]; then
  ravi_run reference --put "$work/read.b:READ.B" --exec 'PICPROG.EXE /LPT1 READ.B' --get DUMP.BIN
  cmp "$work/reference/DUMP.BIN" "$work/payload"
  echo 'PASS: DOSRAVI ran the original driver and retrieved the seeded chip.'
  exit
fi
if [[ ${1:-} == --at28c16 ]]; then
  ravi_run program --put build/dos/PICRF5.COM:PICRF5.COM --put "$work/payload:INPUT.BIN" \
    --exec 'PICRF5.COM WRITE INPUT.BIN 378 PICPROG.LIB 0 2048 AT28C16,P'
  cmp "$work/chip" "$work/payload"
  ravi_run readback --exec 'PICRF5.COM READ DUMP.BIN 378 PICPROG.LIB 0 2048 AT28C16,P' --get DUMP.BIN
  cmp "$work/readback/DUMP.BIN" "$work/payload"
  echo 'PASS: DOSRAVI and the 8086 client programmed and retrieved the AT28C16 image.'
  exit
fi
if [[ ${1:-} == --rf5 ]]; then
  ravi_run program --put build/dos/PICRF5.COM:PICRF5.COM --put "$work/payload:INPUT.BIN" \
    --exec 'PICRF5.COM WRF5 INPUT.BIN 378'
  cmp "$work/chip" "$work/payload"
  ravi_run readback --exec 'PICRF5.COM RRF5 DUMP.BIN 378' --get DUMP.BIN
  cmp "$work/readback/DUMP.BIN" "$work/payload"
  echo 'PASS: DOSRAVI uploaded, programmed and retrieved a matching 2 KiB image.'
  exit
fi
ravi_run session --put build/PPPORTS.COM:PPPORTS.COM --exec PPPORTS.COM
out=$(find "$work/session" -iname stdout.txt -print -quit)
grep -E '^LPT1 base=0378 raw_status=[[:xdigit:]]{2}' "$out"
grep -E '^LPT3 base=' "$out"
cat "$out"
