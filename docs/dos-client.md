# Independent РФ5 DOS client

`PICRF5.COM` is an 8086 DOS program for a single 2 KiB К573РФ5 on the modeled PicProg parallel interface. It reads and writes the PC's LPT registers itself. It neither executes PICPROG.EXE nor opens the virtual chip's backing file. The same file-backed virtual programmer can be started in successive DOS sessions with either client.

## Build and run

Build on Linux with dev86 bcc and NASM, using the same tiny-model ABI and the actual [Willem DOS I/O source](https://github.com/ddanila/willem-v30/blob/afc2d7633ac6599507a5d4842bf73d0eea807284/src/dosio.asm) from the pinned submodule. PicProg uses its byte I/O and PIT wait routines. The two programmers have different LPT wiring and programming sequences, so their device drivers remain separate.

```sh
git submodule update --init
make dos lab
python3 -c 'open("rf5.bin","xb").write(bytes([255])*2048)'
python3 tools/rf5_client_lab.py rf5.bin WRF5 payload.bin
python3 tools/rf5_client_lab.py rf5.bin VRF5 payload.bin
python3 tools/rf5_client_lab.py rf5.bin RRF5 readback.bin
cmp payload.bin readback.bin
```

The lab needs DOSBox-X with Linux ppdev support. In DOS the equivalent commands are `PICRF5 WRF5 PAYLOAD.BIN 378`, `PICRF5 VRF5 PAYLOAD.BIN 378`, and `PICRF5 RRF5 DUMP.BIN 378`. The last argument selects LPT base 378, 278 or 3BC (hex). The full-image interface checks the input size, refuses to replace an existing dump, writes errors to DOS stdout and returns nonzero on failure. WRF5 preflights **all** cells for forbidden 0→1 transitions, skips unchanged cells, checks each programmed byte and verifies the complete part before reporting success. A failure after pulses begin can leave a partially programmed image.

By default the client expects the parallel-register profile already active (ID 07), as it is in the virtual adapter. For optional configuration, append the path to your own 2.77 `PICPROG.LIB` in DOS or pass `--library /path/to/picprog.lib` in the lab. The client validates both 2,778-byte payloads before accessing the port, shifts each LSB first, checks the initial ID and scratch-register loopback, and checks the operating ID. Neither proprietary payload is included here. Each complete bitstream at the virtual LPT boundary was checked against the corresponding original-program trace. This does not validate electrical timing on a physical programmer.

## Using DOSRAVI

The new binary uses the same upload / execute / retrieve workflow as WILLEM.COM. For a DOSRAVI agent connected to the **virtual programmer**, substitute your transport settings:

```sh
dosravi --tcp 127.0.0.1:19572 run \
  --put build/dos/PICRF5.COM:PICRF5.COM --put payload.bin:INPUT.BIN \
  --exec "PICRF5.COM WRF5 INPUT.BIN 378"
dosravi --tcp 127.0.0.1:19572 run \
  --exec "PICRF5.COM RRF5 DUMP.BIN 378" --get DUMP.BIN
```

`make client-test` tests the compiled DOS program without vendor files. `python3 tests/client-roundtrip.py /path/to/Core` adds the configuration trace check and reads each client's programmed image using the other client. `tests/dosravi-smoke.sh --rf5` starts DOSRAVI on an emulated 8086, uploads the new COM and payload, runs two separate commands, and compares the retrieved dump.

**Hardware boundary:** the verified target is the [virtual РФ5 adapter](rf5.md). The reference software's transport profile is 27C64 Quick-Pulse; the adapter translates its programming command into an РФ5 pulse. The independent client implements this register interface. A real PicProg's socket routing, VPP, pulse and cold startup have not been bench-validated for РФ5. An ID match alone does not establish those conditions.
