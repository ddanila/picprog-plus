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
