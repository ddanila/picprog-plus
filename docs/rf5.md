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
