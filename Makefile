build/PPPORTS.COM: src/ppports.asm
	mkdir -p build
	nasm -f bin $< -o $@

.PHONY: test
test: build/PPPORTS.COM
	python3 -m unittest discover -s tests

.PHONY: lab
lab: build/virtual_ppdev.so
build/virtual_ppdev.so: tools/virtual_ppdev.c
	mkdir -p build
	$(CC) -O2 -Wall -Wextra -Werror -shared -fPIC $< -o $@
