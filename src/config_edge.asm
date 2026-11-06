; SPDX-License-Identifier: GPL-2.0-only
; dev86 8086 ABI. Keep each pair of configuration edges adjacent even if a
; timer/serial interrupt arrives; restore the caller's interrupt flag.
BITS 16
SECTION .text
GLOBAL _pp_edge_pair
_pp_edge_pair:
    push bp
    mov bp,sp
    mov dx,[bp+4]
    mov al,[bp+6]
    mov ah,[bp+8]
    pushf
    cli
    out dx,al
    mov al,ah
    out dx,al
    popf
    pop bp
    ret

; Low word of the BIOS tick counter, as used by the reference polling loop.
GLOBAL _pp_ticks
_pp_ticks:
    push es
    mov ax,0x40
    mov es,ax
    mov ax,[es:0x6c]
    pop es
    ret
