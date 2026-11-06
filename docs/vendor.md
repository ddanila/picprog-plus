# Which PicProg?

The [manufacturer's legacy downloads page](https://phyton.ru/zagruzki/) links the [PicProg installer](https://phyton.ru/wp-content/uploads/legacy/SFX/picprog.exe). The downloaded file and a fresh copy from that link were byte-identical. There are two different files called picprog.exe:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| Outer Win32 self-extracting installer | 806519 | d813fa86f47a54383bb469f239fb4b402b9d078da686a66d7d9b64b37eabd530 |
| DOS executable inside Core.rar | 430188 | 3959f7375a9a871364864674ea4a65799da5f81b51294fe98a6e8d52a028183a |

The outer package contains Core.rar and SetupFiles.rar. The former includes the DOS executable, overlay, device library, configuration, help, examples and a CP866 Russian manual (DOC/picprog.txt). Use the DOS executable explicitly: a sample PICPROG.BAT also exists and includes write operations. Package version.ini says 2.75.40; the DOS program's own help banner reports **2.77**.

We ran the DOS program's help in DOSBox-X. It offers LPT1 through LPT4. Although the manual also mentions RS-232, its batch section gives an explicit LPT invocation. For this release the relevant architecture is host → serial DOSRAVI → DOS child → LPT programmer. There is no evidence that the Willem pin-driving routines or device profiles transfer to this programmer.

The batch interface accepts a file after the port option, for example the form PICPROG.EXE /LPT1 filename. The manual describes device selection, reading into a buffer, and saving a binary file. These are application-level commands, not a published parallel-port protocol. The manual names 2716 as a batch default; that does not establish the correct socket placement, supply or programming algorithm for a particular part. We have not verified a 2732A profile or any programming voltage on this unit.

No low-level Phyton protocol specification was found in the material examined. The vendor license is proprietary and restricts reverse engineering. This repository contains original tooling and interface observations. No vendor executable, disassembly listing or configuration payload is redistributed. Obtain the reference application directly from Phyton for any authorized bench comparison.
