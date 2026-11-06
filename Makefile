build/PPPORTS.COM: src/ppports.asm
	mkdir -p build
	nasm -f bin $< -o $@

.PHONY: test
test: build/PPPORTS.COM
	python3 -m unittest discover -s tests
