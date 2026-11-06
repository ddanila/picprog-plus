# Independent РФ5 DOS client

`PICRF5.COM` is an 8086 DOS program for the modeled PicProg parallel interface, with a 2 KiB К573РФ5 adapter or an 8/16 KiB 27C64/27C128 image. It reads and writes the PC's LPT registers itself. It neither executes PICPROG.EXE nor opens the virtual chip's backing file. The same file-backed virtual programmer can be started in successive DOS sessions with either client.

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

The lab needs DOSBox-X with Linux ppdev support. In DOS the equivalent commands are `PICRF5 WRF5 PAYLOAD.BIN 378`, `PICRF5 VRF5 PAYLOAD.BIN 378`, and `PICRF5 RRF5 DUMP.BIN 378`. The port argument selects LPT base 378, 278 or 3BC (hex). The full-image interface checks the input size, refuses to replace an existing dump, writes errors to DOS stdout and returns nonzero on failure. WRF5 preflights **all** cells for forbidden 0→1 transitions, skips unchanged cells, checks each programmed byte and verifies each programmed block before moving to the next. A failure after pulses begin can leave a partially programmed image.

By default the client expects the parallel-register profile already active (ID 07), as it is in the virtual adapter. For optional configuration, append the path to your own 2.77 `PICPROG.LIB` in DOS or pass `--library /path/to/picprog.lib` in the lab. The client validates both 2,778-byte payloads before accessing the port, shifts each LSB first, checks the initial ID and scratch-register loopback, and checks the operating ID. Neither proprietary payload is included here. An explicit device selection sends the operating stream twice after the startup stream. With the library supplied, the full operation is compared at the virtual LPT boundary; see the [parity report](lpt-parity.md). This does not validate electrical timing on a physical programmer.

The vendor-style operation names take a library argument, followed optionally by a decimal start address and byte count. For example, `PICRF5 READ DUMP.BIN 378 PICPROG.LIB 253 263` saves addresses 00FDh–0203h. VERIFY, WRITE and OVERWRITE take an input file exactly as long as the request. CHECK tests for erased bytes and ignores its filename argument. WRITE starts programming immediately; OVERWRITE checks that every requested change is possible first.

For a full 27C64 use an 8192-byte backing image and specify start 0 and length 8192. Example: `PICRF5 WRITE IMAGE.BIN 378 PICPROG.LIB 0 8192 27C64,I` uses Intelligent programming; omit the last token for Quick-Pulse. The lab accepts `--start 0 --length 8192 --profile 27C64,I`. For 27C128, supply a 16384-byte image and select `27C128,Q` or `27C128,I` explicitly. The three short RF5 commands keep their 2048-byte defaults. Partial multi-block writes can access and attempt to program padding beyond the requested end, just as the original does; see the [trace evidence](lpt-parity.md).

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


## Exact reference behavior through DOSRAVI

For a device the independent client does not implement, DOSRAVI can run the original batch program and leave every LPT decision to Phyton. Put your extracted PICPROG.EXE, PICPROG.OVL, PICPROG.LIB and PICPROG.CFG in the agent's working directory. For example, this READ.B reads the 2 KiB virtual adapter through the reference profile:

```text
MESSAGE ON
SET_ROM_TYPE(27C64,Q)
READ(0,2047,0,0)
SAVE("DUMP.BIN",BIN,0,0,2047)
END
```

Save the batch with DOS line endings. The host invocation is:

```sh
dosravi --serial /dev/ttyUSB0 --baud 57600 run --put READ.B:READ.B \
  --exec 'PICPROG.EXE /LPT1 READ.B' --get DUMP.BIN
```

`bash tests/dosravi-smoke.sh --reference /path/to/Core` reproduces this with a temporary DOS drive, emulated 386 and seeded virtual 2 KiB chip; the test compares the entire returned file. Use the independent client for the 8086 target. The reference test does not establish that the proprietary application will run with the CPU and free DOS memory of every laptop.
