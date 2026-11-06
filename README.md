# Phyton PicProg+ for DOSRAVI

An independent start on a DOS driver for the discontinued **Phyton PicProg+** parallel-port programmer. The host link works: DOSRAVI can upload an 8086 DOS program, run it, and collect its output while leaving the parallel port to the program. The first initialization exchange has been reproduced in emulation; the rest of the programmer protocol is unresolved. **No chip read, erase, programming or voltage selection is implemented or hardware verified.** This is a separate project from the [Willem driver](https://github.com/ddanila/willem-v30).

## Try the host-side check

Build with NASM and GNU Make. With [DOSRAVI](https://github.com/ddanila/dosravi) started on the DOS machine, run from the host (substitute the serial device and the agent's baud rate):

```sh
make
dosravi --serial /dev/ttyUSB0 --baud 57600 run \
  --put build/PPPORTS.COM:PPPORTS.COM --exec PPPORTS.COM \
  --note machine=DOS-laptop --note cable-adapter=serial-to-COM1
```

You can do this with the programmer disconnected. PPPORTS lists the first three BIOS LPT entries and samples the raw status register once at each conventional base address. It doesn't write to the port. An entry confirms the host BIOS configured a port; neither its address nor its status byte identifies a PicProg+. Zero means the BIOS entry was empty.

`make test` runs the trace comparison tests. `tests/dosravi-smoke.sh` exercises the actual COM binary via an emulated serial connection and DOSRAVI. It needs DOSBox-X, the installed DOSRAVI Python dependencies and a built DOSRAVI.COM in a sibling dosravi checkout (or set DOSRAVI_DIR). In our DOSBox-X run, the child exited with code 0 and reported LPT1 at 0378 and empty LPT2/3 entries. This tests transport, not electrical behavior.

## Virtual programmer lab

The [Linux virtual LPT lab](docs/virtual-lpt.md) records what the original DOS program writes and can vary the replies without a programmer. A synthetic response passes its first handshake check; the subsequent self-check still fails.

## Where to take the first capture

1. Record the programmer model/revision, cable, power supply, host port base and vendor version. Leave the socket empty. Capture at the **PC–programmer LPT connection**, not at the EPROM socket. Use the cable pinout and analyzer input ratings to identify signal ground, logic levels and channels before connecting. Save the raw acquisition and channel-to-pin map.
2. Capture idle and the vendor software's programmer initialization separately. Repeat with the same configuration. Mark the start of the operation and retain the device's replies as well as host outputs. A port transition during PC boot is not evidence of a programmer command. A disconnected baseline helps distinguish printer-port defaults from responses.
3. Export aligned windows as CSV with header e.g. `time,D0,ACK` and decimal timestamps and 0/1 levels. Run `python3 tools/tracecmp.py first.csv repeat.csv D0 ACK` using the actual channel names. It compares ordered states including the initial level, ignoring repeated samples and timing; the first difference points back to timestamps in the originals. Keep timing in the raw captures for driver development.
4. Once identification is reproducible, implement it and compare against the observed exchange. Then target **read-only acquisition** of a known-good 2 KiB 2716, twice, with each file independently matching the trusted dump. A successful ID alone does not validate the ROM read path. Investigate programming and VPP only after readout is proven for the exact device.

See [download identification and compatibility findings](docs/vendor.md). Original code is GPL-2.0-only; no Phyton code, device libraries, manuals or binaries are included. This project is not affiliated with Phyton.
