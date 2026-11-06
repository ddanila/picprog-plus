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

The observation ends at the deadline if the program is waiting for a key. A timeout is not success. The map selects the returned status byte by the most recent data-port write; other selections return the fixed status. The optional register model does not patch vendor code. The batch saves its result into a fresh guest file so the experiment can distinguish an actual read from a successful launch.

## Evidence from version 2.77

| Experiment | Observable result |
|---|---|
| Help-only, same emulator | One direction setup; no data/control writes or status reads. |
| One-byte read, status fixed at D8 | 88,933 events. After the startup stream, the application samples status 11 times each with data set to 06 and 05. Returns to its communication-error path. Fixed 00 and FF produced the same writes. |
| Return FF after 06, 00 after 05, default D8 | 89,703 events. One status read at each first selector, followed by a new sequence of strobed commands and 16 status reads each at 0D and 0E. |
| Same first gate; default FF | Reaches the same second exchange; the vendor UI then displays communication error (5:383). This is not a successful programmer identification. |

Before the first status read, there are exactly **22,224 four-write groups**. Each is either data 03 → 07 or 02 → 06, followed by control 00 → 04. We counted 18,490 of the former and 3,734 of the latter. Bit 0 varies and bit 2 rises in both cases. This looks like clocking a configuration stream; its destination and semantics have not been established. Treat it as a payload, not as thousands of decoded device commands.

These fixed-reply runs are negative controls; the successful register model is described below. Do not reuse the synthetic values for voltage or programming decisions.

For a targeted hardware comparison, capture the first successful init **before a chip read**, with the socket empty. Trigger on the end of the long repetitive burst, keep data/control plus the return status lines, and compare the two samples at 06/05 and the alternating readbacks at 0D/0E. Preserve the edges around each sample. Those few responses would distinguish a working-device transcript from one that merely satisfies a software check.

At the second exchange, overriding (0D,0E) with (00,00), (FF,00), (00,FF), (80,00), (00,80) or (78,78) gave the same (5:383) error. The displayed number is not a direct readout of those bytes. To test a changing response offline, the map also accepts cyclic status sequences per selector, e.g. `--map 06:ff,05:00,0d:00/ff,0e:ff/00`. Each selector advances only on a status read while that selector is active.

## Register behavior verified with the original reader

In the user's Sourcer v8 listing for the identified DOS EXE, several relevant routines appear as byte declarations. Key entry points in its address notation are 4F50:5D42 (identity comparison), 5E1F (alternating readback), 5EC2 (timing search), 5F99 (strobed nibble write), and 5FE5 (nibble read). The annotated absolute I/O port guesses are misleading: the base is taken from the runtime LPT configuration.

* On a read, the software writes a selector to the data register, samples base+1, and uses bits 7–4 of the last status sample. At the first ID check, 06 supplies the high nibble and 05 the low nibble. The assembled byte must equal the selected descriptor's ID, F0 in the initial mode. After a mismatch the second attempt uses ten samples per selector; the 11 reads per selector in the failing trace are 1 + 10.
* For a nibble write, the high half of the data byte is the value and the low half is the register; control 05 then 04 strobes it. Registers D and E are written with 5 and A and read back; the values swap after each successful pair. A full trial compares 100 pairs. The outer loop searches delay settings. Sixteen failing pairs in the earlier trace were separate failed trials, not a 16-byte identification message.
* After calibration and a second configuration burst, the same ID routine uses 0F (high) and 0C (low). For the observed default 27C64 Quick-Pulse batch run the selected descriptor expects 07. This is a configuration ID, not the contents of the EPROM or a universal reply for all profiles.
* Socket data is assembled in the opposite selector order: 08 gives the low nibble, 09 the high nibble. With the virtual D/E register model, the following run finished and the guest saved **3C**. Changing only 08 to 50 and 09 to A0 yielded **A5**.

```sh
python3 tools/lpt_lab.py /path/to/Core sessions/read-3c.log --echo-de \
  --map 06:f0,05:00,0f:00,0c:70,08:c0,09:30
```

These are raw backend status bytes. The positive runs each had 800 matched pairs during timing calibration. They establish the one-byte software path, not physical connector polarity or safe electrical operation. The separate [РФ5 lab](rf5.md) tests the addressable chip model with full READ and WRITE operations.
