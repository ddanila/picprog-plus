# Which PicProg?

The [manufacturer's legacy downloads page](https://phyton.ru/zagruzki/) links the [PicProg installer](https://phyton.ru/wp-content/uploads/legacy/SFX/picprog.exe). The downloaded file and a fresh copy from that link were byte-identical. There are two different files called picprog.exe:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Outer Win32 self-extracting installer | 806519 | d813fa86f47a54383bb469f239fb4b402b9d078da686a66d7d9b64b37eabd530 |
| DOS executable inside Core.rar | 430188 | 3959f7375a9a871364864674ea4a65799da5f81b51294fe98a6e8d52a028183a |

The outer package contains Core.rar and SetupFiles.rar. The former includes the DOS executable, overlay, device library, configuration, help, examples and a CP866 Russian manual (DOC/picprog.txt). Use the DOS executable explicitly: a sample PICPROG.BAT also exists and includes write operations. Package version.ini says 2.75.40; the DOS program's own help banner reports **2.77**.

We ran the DOS program's help in DOSBox-X. It offers LPT1 through LPT4. Although the manual also mentions RS-232, its batch section gives an explicit LPT invocation. For this release the relevant architecture is host → serial DOSRAVI → DOS child → LPT programmer. There is no evidence that the Willem pin-driving routines or device profiles transfer to this programmer.

The batch interface accepts a file after the port option, for example the form PICPROG.EXE /LPT1 filename. The manual describes device selection, reading into a buffer, and saving a binary file. These are application-level commands, not a published parallel-port protocol. The manual names 2716 as a batch default. Inspection of the running 2.77 descriptor and an explicit batch selection identify the profile used in our tests as 27C64 Quick-Pulse; see the [РФ5 model](rf5.md). We have not verified a 2732A profile or any programming voltage on this unit.

No low-level Phyton protocol specification was found in the material examined. The vendor license is proprietary and restricts reverse engineering. This repository contains original tooling and interface observations. No vendor executable, disassembly listing or configuration payload is redistributed. Obtain the reference application directly from Phyton for any authorized bench comparison.

## Owner's PicProg+ board

The owner reports an ATT3030-100 FPGA, Altera EP220PC-12, UDN2595A, and two UCN5891A chips. No PCB routing or voltages are confirmed by these markings.

- The [ATT3030 configuration table](https://www.tautec-electronics.de/Datenblaetter/Schaltkreise/ATT3030.pdf) gives 22,216 bits including the header (2,777 bytes). The [observed host configuration transfers](dos-client.md) are 2,778 bytes. The near match supports an FPGA configuration interpretation; it does not explain the extra byte or identify a VPP command. The [Altera EP220](https://www.artisantg.com/info/Intel_Altera_EP220PC_12_Datasheet_2019225151830.pdf) is programmable logic; its board-specific function is unknown.
- Each [Allegro UCN5891A](https://www.allegromicro.com/~/media/Files/Datasheets/UCN5890-1-Datasheet.ashx) has eight latched high-side outputs supplied from a common external VBB. DIP pin 13 is VBB, pin 15 is the separate logic supply, pin 1 is ground, and pins 5–12 are the outputs. The [UDN2595A](https://www.allegromicro.com/-/media/files/datasheets/udn-a2595-datasheet.ashx) is an eight-channel low-side driver. These parts can switch power; their presence does not establish which voltages are available at the socket.
- First continuity check: disconnect power and LPT, leave the ZIF empty, and measure pin 13 to pin 13 across the two UCN5891As. Near-zero resistance in both directions suggests a common rail; an open reading calls for tracing the supplies separately. Neither result establishes the voltage. To qualify a programming profile, match the exact EPROM datasheet and measure the programming pulse at its socket contact.
