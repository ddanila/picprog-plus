# Observing the DOS application at LPT1

On Linux we run the unmodified vendor DOS executable and replace only DOSBox-X's parallel-port endpoint. A small ioctl shim answers ppdev requests for one temporary regular file. This is an experimental model of the interface visible to the host; there is no physical I/O and no device firmware is included. The trace records register operations, not electrical levels or timing. WD/WC are writes to data/control; RS/RC are status/control reads. Hex values are in the ppdev backend's representation.

## Repeat locally

Install DOSBox-X with Linux ppdev support, Linux userspace headers and a C compiler. Supply a privately extracted DOS Core directory (see [package identification](vendor.md)); do not point this at the Windows installer. The runner copies the directory into a disposable drive and uses a fresh one-byte READ batch file. It does not use the vendor's example write batch. Traces can contain a full serial payload: keep them private.

```sh
make lab
mkdir -p sessions
python3 tools/lpt_lab.py /path/to/Core sessions/help.log --help-only
python3 tools/lpt_lab.py /path/to/Core sessions/constant.log --status 0xd8
python3 tools/lpt_lab.py /path/to/Core sessions/selected.log --map 06:ff,05:00
```

The observation ends at the deadline if the program is waiting for a key. A timeout is not success. The map selects the returned status byte by the most recent data-port write; other selections return the fixed status. It does not use instruction addresses, patch vendor code, or pretend the requested ROM read succeeded.

## Evidence from version 2.77

| Experiment | Observable result |
|---|---|
| Help-only, same emulator | One direction setup; no data/control writes or status reads. |
| One-byte read, status fixed at D8 | 88,933 events. After the startup stream, the application samples status 11 times each with data set to 06 and 05. Returns to its communication-error path. Fixed 00 and FF produced the same writes. |
| Return FF after 06, 00 after 05, default D8 | 89,703 events. One status read at each first selector, followed by a new sequence of strobed commands and 16 status reads each at 0D and 0E. |
| Same first gate; default FF | Reaches the same second exchange; the vendor UI then displays communication error (5:383). This is not a successful programmer identification. |

Before the first status read, there are exactly **22,224 four-write groups**. Each is either data 03 → 07 or 02 → 06, followed by control 00 → 04. We counted 18,490 of the former and 3,734 of the latter. Bit 0 varies and bit 2 rises in both cases. This looks like clocking a configuration stream; its destination and semantics have not been established. Treat it as a payload, not as thousands of decoded device commands.

The two response-dependent paths provide a regression target for the first handshake. The later data selectors are consistent with multiplexed readback, but the trace alone does not say whether a reply represents an ID, a measurement, memory or a self-test. Do not reuse the synthetic values for voltage or programming decisions.

For a targeted hardware comparison, capture the first successful init **before a chip read**, with the socket empty. Trigger on the end of the long repetitive burst, keep data/control plus the return status lines, and compare the two samples at 06/05 and the following 16 pairs at 0D/0E. Preserve the edges around each sample. Those few responses would distinguish a working-device transcript from one that merely satisfies a software check.

At the second exchange, overriding (0D,0E) with (00,00), (FF,00), (00,FF), (80,00), (00,80) or (78,78) gave the same (5:383) error. The displayed number is not a direct readout of those bytes. To test a changing response offline, the map also accepts cyclic status sequences per selector, e.g. `--map 06:ff,05:00,0d:00/ff,0e:ff/00`. Each selector advances only on a status read while that selector is active.
