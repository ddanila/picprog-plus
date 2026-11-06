# Comparing PICRF5.COM with Phyton 2.77

The reference is the [identified DOS binary and overlay](vendor.md), running a batch that explicitly selects `SET_ROM_TYPE(27C64,Q)`. Both it and our independent 8086 client talk to the same [virtual programmer and 2 KiB chip](rf5.md), in separate DOSBox-X sessions starting with identical chip contents. A match means **every logged data write, control write and read result is identical and in order**, including repeated writes. We also compare the resulting chip and any dumped file. These are digital register traces; they contain no elapsed times or socket voltages.

| Operation | Full 2 KiB: matching events | 00FDh–0203h: matching events |
|---|---:|---:|
| READ | 356,505 | 336,065 |
| CHECK (erased) | 356,505 | 336,065 |
| VERIFY | 356,505 | 336,065 |
| WRITE | 478,634 | 357,821 |
| OVERWRITE | 491,646 | 360,459 |

Counts are for the default fixture seed, 1715. Equal counts for the three read operations do not imply identical returned data. Fault tests cover a nonblank cell, a verify mismatch, an impossible 0→1 transition, two missed programming pulses followed by success, and exhaustion of the 25 attempts. For operator errors we compare through the original program's wait for input; PICRF5 reports the failing address and exits instead.

## What changed in the driver

* At startup, load the initial configuration, calibrate control-port strobes by writing and reading alternating scratch values, and load the operating configuration. The batch's explicit device selection loads that operating configuration again. Probe the programmer revision and check socket response after first driving FFh and then 00h.
* Reproduce the original serial setup words, register shadow and address/data nibble ordering. A serial transfer invalidates the cached data nibbles. Omitting even a redundant strobe or an input read fails the comparison.
* Before programming a block, shift 04h and write 47h (register 7 ← 4). For a changed byte, write 26h, present the data, and write 8Eh then CEh with a nominal 100 µs wait between them. Check status, re-enable reading and compare the byte. Retry until it matches or the profile's 25 attempts are exhausted. Before block verification write 07h and shift 06h. These values are encoded **commands**, not volts.
* In a multi-block partial write the original can continue through the end of its last 256-byte block, treating the unused tail as FFh. We match that behavior on erased padding. Our client refuses to pulse populated padding outside the requested range and caps accesses at the modeled chip boundary.

Useful offsets in the DOS EXE for checking against a local listing: 0x320CF (scratch test), 0x32172 (strobe calibration), 0x32217 (cached nibble writes), 0x33671 (program retries), 0x3373D (pulse), 0x3393C (socket check). Vendor code and its configuration streams are not distributed here.

## Reproduce and interpret the result

Run `make parity-test CORE=/path/to/extracted/Core` with DOSBox-X, dev86, NASM and the submodule installed. To repeat with other image contents, run `python3 tests/lpt-parity.py /path/to/Core --seed 42 --faults`. No real programmer is accessed.

This establishes parity for these operations and fixtures on **one** device profile. It does not establish timings at the pins, the analog meaning of the serial words, or a safe programming voltage for an actual РФ5. The reference profile is 27C64 Quick-Pulse; the adapter supplies the simulated РФ5 pulse. Other devices, algorithms, PIC configuration words and protection operations, negative startup responses, and actions after an interactive error prompt require separate reference cases. The generic Phyton DOS application is not reimplemented by this client.

### Which other EPROM profiles did the original actually accept?

We also ran selection-only batches (`MESSAGE ON`, `SET_ROM_TYPE`, print a completion marker) against the same executable and library. This distinguishes a valid starting point for the next comparison from a name that appears only in the manual. No chip was programmed in this experiment.

| Batch selection | Reference result |
|---|---|
| 27C64,Q / 27C64,I | Both accepted, 2000h bytes; Quick-Pulse / Inteligent respectively |
| 27C256,Q | Accepted, 8000h bytes, Quick-Pulse |
| 27C512,Q | Accepted, 10000h bytes, Quick-Pulse |
| 2716,I / 2716,Q / 2732,I / 2732A,I / 2764,I | Rejected at device selection: invalid ROM type |

In particular, the manual's 2764,I example fails in this release. These results apply to the exact batch spellings tested, not every device the physical programmer can support. The most direct comparison for isolating algorithm differences is 27C64,I versus 27C64,Q: same family and size, different programming algorithm. Full-capacity tests also need a chip model with more than eleven address bits; otherwise high addresses alias into the 2 KiB image and can give misleading results.
