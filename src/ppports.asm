; SPDX-License-Identifier: GPL-2.0-only
; DOS .COM, no OUT or BIOS printer calls. Inventory the host, not the target.
bits 16
cpu 8086
org 100h
start:
    mov dx, banner
    call print
    mov ax, 40h
    mov es, ax
    mov si, 8                    ; BIOS data area: conventional LPT1..3 words
    mov bp, 1
.next:
    mov dx, prefix
    call print
    mov ax, bp
    add al, '0'
    call put
    mov dx, base_msg
    call print
    mov bx, [es:si]
    mov ax, bx
    call hexword
    cmp bx, 378h
    je .sample
    cmp bx, 278h
    je .sample
    cmp bx, 3bch
    jne .skip
.sample:
    mov dx, status_msg
    call print
    mov dx, bx
    inc dx
    in al, dx                    ; raw status only, no signal toggles
    call hexbyte
.skip:
    mov dx, newline
    call print
    add si, 2
    inc bp
    cmp bp, 4
    jne .next
    mov ax, 4c00h
    int 21h
hexword:
    push ax
    mov al, ah
    call hexbyte
    pop ax
hexbyte:
    push ax
    mov cl, 4
    shr al, cl
    call nibble
    pop ax
nibble:
    and al, 15
    cmp al, 10
    jb .number
    add al, 7
.number:
    add al, '0'
put:
    mov dl, al
    mov ah, 2
    int 21h
    ret
print:
    mov ah, 9
    int 21h
    ret
banner db 'PPPORTS 1 - BIOS port inventory only',13,10,'$'
prefix db 'LPT$'
base_msg db ' base=$'
status_msg db ' raw_status=$'
newline db 13,10,'$'
