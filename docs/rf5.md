# Reading and programming a virtual К573РФ5

The virtual chip has eleven address lines, eight data lines and 2,048 persistent bytes. A blank image contains FF at every address. Programming can clear bits; subsequent pulses cannot set them again. The model distinguishes read, disabled output and program conditions. There is no electric erase operation. [Lebedev's memory handbook, table for К573РФ2/РФ5](https://www.computer-museum.ru/books/radio/mrb1152.pdf) describes the nominal CS programming pulse, OE level and programming supply for this family.

**The chip model and the DOS device selection are separate.** Despite the bundled manual's 2716 default, the active first descriptor in this release is family **27C64, Quick-Pulse, size 2000h**. The batch interpreter rejected `SET_ROM_TYPE(2716,I)`. The lab explicitly selects the working 27C64 command path and restricts operations to 0000h–07FFh. A software adapter turns its programming command into a nominal 50 ms РФ5 pulse, in simulated time. The model does not claim a 50 ms physical threshold, model analog voltages, or establish a real adapter pinout. **Do not use the lab's 27C64 selection to program a physical РФ5.**

## Use it

On Linux, install DOSBox-X with ppdev support, a C compiler and Python 3.10+. Supply your own extracted PicProg 2.77 Core directory. All LPT actions below terminate at a regular temporary file, not a hardware port. Each invocation launches a fresh DOS session. The chip image persists independently of the DOS buffer.

```sh
make lab
# Create a new erased image; fail if the file already exists.
python3 -c 'open("rf5.bin","xb").write(bytes([255])*2048)'
python3 tools/rf5_lab.py /path/to/Core rf5.bin write payload.bin
python3 tools/rf5_lab.py /path/to/Core rf5.bin read readback.bin
cmp payload.bin readback.bin   # for a full-size payload
```

For partial writes, add e.g. `--start 0x100`; the input length determines the range. Reads accept both `--start` and `--size` and require a new output file. The runner refuses an out-of-range request or a requested 0-to-1 transition before starting DOS. It selects WRITE on erased ranges and OVERWRITE for additional bit clearing. Once programming starts the image can be partially programmed if the guest is interrupted, like a chip on the bench.

## What the adapter decodes

Strobed writes latch the high half of the data-port byte as the value of the register selected by its low half. In this DOS profile, registers 2, 3 and D supply the address in ascending nibble order; only A0–A10 connect to the virtual chip. Registers 0 and 1 hold outgoing data, low nibble first. Readback uses status selectors 8 and 9. After configuration, the observed programming command transitions E from 8 to C with register 7 at 4 and register 6 at 2. Only that qualified event programs the addressed byte. The adapter reports completion immediately; a read in output mode retrieves the stored byte, not the last byte sent by the host.

## Verification

`make test` checks the socket model, including disabled outputs, pulse qualification and irreversible bit clearing. For an end-to-end test with the original DOS application:

```sh
make lab
python3 tests/rf5-roundtrip.py /path/to/Core
```

This reads an independently seeded chip, programs a fresh erased chip with a different deterministic image, and compares a fresh-session DOS read and the full backing file with that input. It also programs across 00FFh/0100h, checks the neighbors, and rejects impossible and out-of-range writes. The golden 2 KiB input and the verified full readback have SHA-256 `139c58631e4784e1829c6e9dfa0c7dbb9e67f8c3ed51f2526bc3f12b60fc2850`.

## What the original does for 2716, РФ2 and РФ5

There are two different paths in the [Phyton DOS release](vendor.md). The bundled manual calls 2716 the *batch default*. That does not mean that 2716 is a selectable device. With the shipped PICPROG.CFG (SHA-256 `02f6561e055b88393a23929ee71034c20fcd4c25a8f0036ae8f93de58f3047ec`), we observed:

| Original batch | Observed result |
|---|---|
| No SET_ROM_TYPE; READ, VERIFY, CHECK, WRITE or OVERWRITE over 0000h–07FFh | All five completed on the 2 KiB virtual adapter. The independent client's `DEFAULT` mode matches every ppdev event, including startup and shutdown. |
| No SET_ROM_TYPE; READ across 07FFh into 0800h | The interpreter reported the PROM range error before the read, even with an 8 KiB device attached in the lab. |
| SET_ROM_TYPE with 2716,I; 2716,Q; U2716C35,I; K573RF2,I; K573RF5,I | Invalid ROM type. The trace is identical to an empty batch: 241,417 startup events, then no chip operation. |
| CP866 К573РФ2,I; К573РФ5,I; РФ2,I; РФ5,I | Same startup trace; no dump or chip change within 20 seconds. No confirmed error message from Phyton for these spellings. PICRF5 returns an error instead of waiting. |

A bare `READ()` with neither a device selection nor an address range also reads exactly 2,048 bytes. The default path loads the startup and operating streams once each. Explicitly selecting 27C64,Q loads the operating stream a second time. While running at its 2 KiB batch default, 2.77 still drives the observed Quick-Pulse hardware interface. Neither this traffic nor a successful virtual read establishes socket routing, VPP or a programming pulse for a physical 2716, РФ2 or РФ5.

To reproduce the default in the **virtual lab**:

```sh
make dos lab
python3 tools/rf5_client_lab.py chip.bin READ dump.bin --library /path/to/Core/picprog.lib --profile DEFAULT
make parity-2716 CORE=/path/to/Core IMAGE=/path/to/2048-byte-rom.bin
```

The optional IMAGE is copied into temporary fixtures. We used the [MB002 inventory acquisition](https://github.com/ddanila/vintage-computer-inventory/blob/main/items/MB002-robotron-pc1715/BENCH.md), SHA-256 `51cb80639b5667f2611da71ce7305061566cf3474bda7db6fc82709d08e46d01`. Its exact chip marking is unconfirmed. The full-image READ and VERIFY matched at 266,640 events each. WRITE onto erased cells matched at 382,068 and OVERWRITE onto partially programmed cells at 402,774; both resulting images matched the acquisition byte-for-byte. CHECK used a blank image. The ROM was not redistributed or re-read from hardware.

### Partial writes and defective cells

The default WRITE and OVERWRITE both scan beyond 07FFh for a 257-byte
request starting at 06FFh. With 11 socket address bits the padding aliases
cell 0000h. A nonblank sentinel there leaves the requested bytes programmed
but causes retry exhaustion at bus address 0800h. The sentinel is unchanged.
On an 8 KiB control chip the same sentinel does not interfere. Single-byte
and aligned 256-byte requests ending at 07FFh complete normally.
`make parity-2716` includes these comparisons and a partially programmable
cell. Set `PP_STUCK_CELL=7fb:01` to inhibit clearing bit zero at physical
address 07FBh in the EPROM model. It affects the stored byte only; all
readbacks use actual cell contents.

### First bench comparison (read only; not yet performed)

1. Record the PicProg+ revision, supply, cable and LPT base. Establish
   the actual socket orientation and routing for the specific MB002 part
   or adapter from its marking, device documentation and continuity with
   power disconnected. The exact Soviet part number in the inventory is
   unconfirmed; the 27C64 software selection is not a wiring diagram.
2. With the socket empty, observe power-up, initialization and READ.
   Check ground, VCC, VPP and control levels at the intended chip contacts
   against that part's read ratings, including transitions. Use a scope for
   transients a meter cannot resolve. An empty-socket rejection may prevent
   the complete read sequence: in that case establish the remaining levels
   with a breakout/test load before connecting the ROM.
3. Only after routing and levels are established, power down, insert the ROM,
   and acquire two full dumps to separate files using fresh sessions. Retrieve
   both via DOSRAVI. Compare the files and their SHA-256 with the MB002
   reference above; retain raw dumps, logs and setup notes. On disagreement,
   keep both and investigate. Two matching reads validate readout, not VPP or
   a physical programming cycle. No WRITE or OVERWRITE is part of this check.
