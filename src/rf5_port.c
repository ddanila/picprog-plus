/* SPDX-License-Identifier: GPL-2.0-only
 * PicProg configured-register interface. Transport uses Willem's dev86 ABI;
 * no Willem pin routing or pulse algorithm applies to PicProg.
 */
#include "rf5_port.h"
extern void dos_outb(unsigned port, unsigned value);
extern unsigned dos_inb(unsigned port);
static unsigned base;

void pp_base(unsigned port) { base = port; }

static void latch(unsigned reg, unsigned value)
{
    dos_outb(base, ((value & 15) << 4) | reg);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 4);
}

static unsigned sample(unsigned reg)
{
    dos_outb(base, reg);
    return (dos_inb(base + 1) >> 4) & 15;
}

int pp_identify(void)
{
    unsigned hi, lo;
    hi = sample(15);
    lo = sample(12);
    return hi == 0 && lo == 7;
}

void pp_idle(void)
{
    latch(7, 0);
    latch(6, 4);
    dos_outb(base, 0);
    dos_outb(base + 2, 11);
}

static void select_address(unsigned address)
{
    latch(2, address);
    latch(3, address >> 4);
    latch(13, address >> 8);
}

unsigned pp_read(unsigned address)
{
    unsigned lo;
    latch(6, 4);
    select_address(address);
    lo = sample(8);
    return lo | (sample(9) << 4);
}

int pp_program(unsigned address, unsigned value)
{
    unsigned fault;
    select_address(address);
    latch(7, 4);
    latch(6, 2);
    latch(0, value);
    latch(1, value >> 4);
    latch(14, 8);
    latch(14, 12);
    fault = sample(4) & 1;
    latch(7, 0);
    latch(6, 4);
    return !fault;
}

extern void dos_wait_us(unsigned usec);

static int stream(unsigned char *bytes)
{
    unsigned i, bit, data;
    dos_outb(base, 0);
    dos_outb(base + 2, 11);
    dos_outb(base, 255);
    dos_outb(base + 2, 6);
    dos_wait_us(2000);
    dos_outb(base + 2, 14);
    dos_wait_us(2000);
    dos_outb(base + 2, 6);
    dos_wait_us(2000);
    dos_outb(base + 2, 4);
    dos_wait_us(5000);
    for (i = 0; i < PP_STREAM_SIZE; ++i) {
        for (bit = 1; bit < 256; bit <<= 1) {
            data = (bytes[i] & bit) ? 3 : 2;
            dos_outb(base, data);
            dos_outb(base, data | 4);
            dos_outb(base + 2, 0);
            dos_outb(base + 2, 4);
        }
    }
    return !(dos_inb(base + 2) & 2);
}

int pp_configure(unsigned char *startup, unsigned char *parallel)
{
    unsigned i, d, e;
    if (!stream(startup) || sample(6) != 15 || sample(5) != 0) return 0;
    latch(7, 0);
    /* Validate the nibble register loopback before loading the device profile.
       Use conservative I/O settling instead of searching for maximum speed. */
    for (i = 0; i < 100; ++i) {
        d = (i & 1) ? 10 : 5;
        e = 15 - d;
        latch(13, d);
        latch(14, e);
        if (sample(13) != d || sample(14) != e) return 0;
    }
    return stream(parallel) && pp_identify();
}
