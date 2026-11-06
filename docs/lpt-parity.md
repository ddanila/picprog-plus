# Comparing PICRF5.COM with Phyton 2.77

The reference is the [identified DOS binary and overlay](vendor.md), running a batch that explicitly selects the algorithm under test (for example `SET_ROM_TYPE(27C64,Q)`). Both it and our independent 8086 client talk to the same virtual programmer, with either the [2 KiB РФ5 adapter](rf5.md) or a directly addressed 8 or 16 KiB EPROM image, in separate DOSBox-X sessions starting with identical chip contents. A match means **every logged data write, control write and read result is identical and in order**, including repeated writes. We also compare the resulting chip and any dumped file. These are digital register traces; they contain no elapsed times or socket voltages.

| Operation | Full 2 KiB: matching events | 00FDh–0203h: matching events | Full 8 KiB, Quick-Pulse |
|---|---:|---:|---:|
| READ | 356,505 | 336,065 | 426,959 |
| CHECK (erased) | 356,505 | 336,065 | 426,959 |
| VERIFY | 356,505 | 336,065 | 426,959 |
| WRITE | 478,634 | 357,821 | 915,701 |
| OVERWRITE | 491,646 | 360,459 | 965,840 |

Counts are for the default fixture seed, 1715. Equal counts for the three read operations do not imply identical returned data. Fault tests cover a nonblank cell, a verify mismatch, an impossible 0→1 transition, two missed programming pulses followed by success, and exhaustion of the 25 attempts. Startup cases include rejected startup and operating IDs, failing scratch readback and a floating socket. We separately inject a programmer-reported pulse fault, which takes a different shutdown path than retry exhaustion. For operator errors we compare through the original program's wait for input; PICRF5 reports the failing address and exits instead.

## What changed in the driver

* At startup, load the initial configuration, calibrate control-port strobes by writing and reading alternating scratch values, and load the operating configuration. The batch's explicit device selection loads that operating configuration again. Probe the programmer revision and check socket response after first driving FFh and then 00h.
* Reproduce the original serial setup words, register shadow and address/data nibble ordering. A serial transfer invalidates the cached data nibbles. Omitting even a redundant strobe or an input read fails the comparison.
* Before programming a block, shift 04h and write 47h (register 7 ← 4). For a changed byte, write 26h, present the data, and write 8Eh then CEh with a nominal 100 µs wait between them. Check status, re-enable reading and compare the byte. Retry until it matches or the profile's 25 attempts are exhausted. Before block verification write 07h and shift 06h. These values are encoded **commands**, not volts.
* In a multi-block partial write the original can continue through the end of its last 256-byte block, treating the unused tail as FFh. The client follows the original even on nonblank padding: it attempts FFh, cannot restore cleared bits, exhausts its retries and reports the failing address. An eleven-pin adapter can alias bus addresses past 07FFh; the driver sends the original addresses, even there.

Useful offsets in the DOS EXE for checking against a local listing: 0x320CF (scratch test), 0x32172 (strobe calibration), 0x32217 (cached nibble writes), 0x33671 (program retries), 0x3373D (pulse), 0x3393C (socket check). Vendor code and its configuration streams are not distributed here.

## Reproduce and interpret the result

Run `make parity-test CORE=/path/to/extracted/Core` with DOSBox-X, dev86, NASM and the submodule installed. To repeat with other image contents, run `python3 tests/lpt-parity.py /path/to/Core --seed 42 --faults`. No real programmer is accessed.

This establishes parity for the tested operations, replies and fixtures. It does not establish timings at the pins, the analog meaning of the serial words, or a safe programming voltage for an actual РФ5. The reference profile is 27C64 Quick-Pulse; the adapter supplies the simulated РФ5 pulse. Other devices, algorithms, PIC configuration words and protection operations, untested programmer replies, and actions after an interactive error prompt require separate reference cases. The generic Phyton DOS application is not reimplemented by this client.

### Which other EPROM profiles did the original actually accept?

We also ran selection-only batches (`MESSAGE ON`, `SET_ROM_TYPE`, print a completion marker) against the same executable and library. This distinguishes a valid starting point for the next comparison from a name that appears only in the manual. No chip was programmed in this experiment.

| Batch selection | Reference result |
|---|---|
| 27C64,Q / 27C64,I | Both accepted, 2000h bytes; Quick-Pulse / Inteligent respectively |
| 27C128,Q / 27C128,I | Both accepted; compared across 1FFFh/2000h on a 16 KiB image |
| 27C256,Q | Accepted, 8000h bytes, Quick-Pulse |
| 27C512,Q | Accepted, 10000h bytes, Quick-Pulse |
| 2716,I / 2716,Q / 2732,I / 2732A,I / 2764,I | Rejected at device selection: invalid ROM type |

In particular, the manual's 2764,I example fails in this release. These results apply to the exact batch spellings tested, not every device the physical programmer can support. For both 27C64,I and 27C128,I we inspected the active device descriptor at the first pulse: its attempt limit is 25, delay parameter 10, and overprogram flag 1. For Q the same fields are 25, 1, 0. In I mode the first matching readback triggers a further pulse of three times the base duration times the number of attempts, followed by readback. Nominal base durations are 1 ms (I) and 100 µs (Q). We compare both a normal write and a write that takes three attempts. Wall-clock pulse width is not part of the ppdev trace.

The separate 8 KiB model decodes A12 from the low bit of register E; the pulse and shutdown sequence must preserve or clear that bit at the same points as the original. The original 2 KiB adapter still aliases it. An 8 KiB fixture uses independently seeded data across that boundary. A full 27C64 Intelligent WRITE matches 1,193,277 events; OVERWRITE matches 1,225,940. For 27C128 both algorithms were compared across 1FFFh/2000h; a separate check at 3FF0h–3FFFh reached the last physical address.

### Scope of the complete programmer

`python3 tools/profile_inventory.py /path/to/Core/picprog.exe` counts the device/algorithm rows in the identified reference executable; add `--list` for manufacturer, device and algorithm. There are 460 catalog entries: 271 Serial, 84 External, 48 Polling, 33 Quick-Pulse, 16 Parallel, four Inteligent and four PRESTO II. These are catalog entries, not 460 distinct sets of LPT routines. The independent driver implements Quick-Pulse and Intelligent for 27C64 and 27C128. The other 456 entries are not certified by these tests. For example, a one-byte write with a 27C256,Q or 27C512,Q selection does not complete against this 27C64 socket model. Unlike 27C64, 27C256,Q toggles register 6 from 2 to 3 during a pulse; 27C512,Q also gates register 7 around each pulse. Selecting a device successfully is insufficient evidence that its programming sequence is implemented.
