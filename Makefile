build/PPPORTS.COM: src/ppports.asm
	mkdir -p build
	nasm -f bin $< -o $@

.PHONY: test
test: build/PPPORTS.COM build/test-rf5
	./build/test-rf5
	python3 -m unittest discover -s tests

.PHONY: lab
lab: build/virtual_ppdev.so
build/virtual_ppdev.so: tools/virtual_ppdev.c tools/rf5_chip.h
	mkdir -p build
	$(CC) -O2 -Wall -Wextra -Werror -shared -fPIC $< -o $@

build/test-rf5: tests/rf5_socket.c tools/rf5_chip.h
	mkdir -p build
	$(CC) -Wall -Wextra -Werror -std=c99 $< -o $@

# Match willem-v30's 8086 ABI and tiny .COM link model.
DOSFLAGS = -0 -Md -ansi -O
.PHONY: dos
dos: build/dos/PICRF5.COM
build/dos/%.o: src/%.c src/rf5_port.h
	mkdir -p build/dos
	bcc $(DOSFLAGS) -Isrc -c $< -o $@
build/dos/dosio.o: third_party/willem-v30/src/dosio.asm
	mkdir -p build/dos
	nasm -f as86 $< -o $@
build/dos/config_edge.o: src/config_edge.asm
	mkdir -p build/dos
	nasm -f as86 $< -o $@
build/dos/PICRF5.COM: build/dos/rf5_main.o build/dos/rf5_port.o build/dos/dosio.o build/dos/config_edge.o
	bcc -0 -Md -i -o $@ $^

.PHONY: client-test
client-test: dos lab
	python3 tests/client-roundtrip.py

.PHONY: parity-test
parity-test: dos lab
	@test -n "$(CORE)" || { echo 'Set CORE to the extracted Phyton 2.77 Core directory'; exit 2; }
	python3 tests/lpt-parity.py "$(CORE)" --faults
