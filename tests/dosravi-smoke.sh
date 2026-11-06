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
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy dosbox-x -silent -fastlaunch \
  -set 'sdl output=surface' -set 'cpu cputype=8086' -set 'cpu cycles=max' \
  -set 'parallel parallel1=file' \
  -set "serial serial1=nullmodem port:$port transparent:1 telnet:0 usedtr:0 rxdelay:0 txdelay:0" \
  -c "mount c $work" -c 'c:' -c 'cd RAVI' \
  -c 'echo ready > READY' -c 'DOSRAVI.COM /COM1 /BAUD:57600 /ROOT:C:\RAVI' >"$work/emulator.log" 2>&1 &
pid=$!
for _ in {1..100}; do [[ -f "$work/RAVI/READY" ]] && break; sleep .1; done
[[ -f "$work/RAVI/READY" ]] || { cat "$work/emulator.log"; exit 1; }
sleep 1  # allow the DOS agent to initialize its UART after the shell marker
PYTHONPATH="$ravi" python3 -m dosravi.cli --tcp "127.0.0.1:$port" --baud 57600 \
  --session-dir "$work/session" run --put build/PPPORTS.COM:PPPORTS.COM \
  --exec PPPORTS.COM --note machine=DOSBox-X --note cable-adapter=nullmodem
out=$(find "$work/session" -iname stdout.txt -print -quit)
grep -E '^LPT1 base=0378 raw_status=[[:xdigit:]]{2}' "$out"
grep -E '^LPT3 base=' "$out"
cat "$out"
