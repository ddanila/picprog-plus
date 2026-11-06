/* SPDX-License-Identifier: GPL-2.0-only
 * PicProg configured-register interface. Transport uses Willem's dev86 ABI;
 * no Willem pin routing or pulse algorithm applies to PicProg.
 */
#include "rf5_port.h"
extern void dos_outb(unsigned port, unsigned value);
extern unsigned dos_inb(unsigned port);
static unsigned base;
static unsigned hold = 1;

void pp_base(unsigned port) { base = port; }

static void latch(unsigned reg, unsigned value)
{
    unsigned n;
    dos_outb(base, ((value & 15) << 4) | reg);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 5);
    dos_outb(base + 2, 5);
    for (n = 0; n < hold; ++n) dos_outb(base + 2, 4);
}

static unsigned sample(unsigned reg)
{
    dos_outb(base, reg);
    return (dos_inb(base + 1) >> 4) & 15;
}

extern void dos_wait_us(unsigned usec);
extern void pp_edge_pair(unsigned port, unsigned first, unsigned second);

static int stream(unsigned char *bytes)
{
    unsigned i, bit, data;
    dos_outb(base, 0);
    dos_outb(base + 2, 11);
    dos_outb(base, 255);
    dos_outb(base + 2, 6);
    dos_wait_us(20);
    dos_outb(base + 2, 14);
    dos_wait_us(20);
    dos_outb(base + 2, 6);
    dos_wait_us(20);
    dos_outb(base + 2, 4);
    dos_wait_us(500);
    for (i = 0; i < PP_STREAM_SIZE; ++i) {
        for (bit = 1; bit < 256; bit <<= 1) {
            data = (bytes[i] & bit) ? 3 : 2;
            pp_edge_pair(base, data, data | 4);
            pp_edge_pair(base + 2, 0, 4);
            dos_wait_us(10);
        }
    }
    dos_wait_us(10);
    return !(dos_inb(base + 2) & 2);
}

/* The 2.77 family-27C64 transport used by the RF5 virtual adapter.
 * These are programmer register numbers and shift words, not measured volts. */
static unsigned char latched[16];
static void wr(unsigned packed)
{
    latched[packed & 15] = packed >> 4;
    latch(packed & 15, packed >> 4);
}
static void changed(unsigned r, unsigned v)
{
    v &= 15;
    if (latched[r] != v) wr((v << 4) | r);
}
static void shift(unsigned value)
{
    unsigned i, j;
    for (i = 0; i < 8; ++i) {
        dos_outb(base, value & 1);
        dos_outb(base+2, 0);
        for (j = 0; j < 15; ++j) dos_outb(base+2, 4);
        value >>= 1;
    }
    /* A serial shift invalidates the parallel data shadow. */
    latched[0] = latched[1] = 255;
}
static void serial_clock(unsigned value)
{
    unsigned n, bit;
    for (n = 0; n < 8; ++n) {
        bit = (value & 1) << 4;
        wr(5 | bit); wr(0x45 | bit);
        value >>= 1;
    }
    wr(0x85);
}
static void transfer(unsigned value)
{
    shift(value); wr(0xb5); wr(0xa5);
}
static void zero_serial(void)
{
    shift(0); wr(0x67); wr(0x47); transfer(0); wr(0x85);
}
/* A new configuration invalidates the host's register shadow. The middle
 * boot phase keeps the cleared low address registers from the first stage. */
static void reset_profile(int middle)
{
    serial_clock(0xf7); wr(7); wr(0x46);
    if (!middle) { wr(2); wr(3); }
    wr(13); wr(0xce); wr(0x8e); wr(14);
    if (!middle) wr(15);
    zero_serial();
}
static void park_profile(void)
{
    serial_clock(0xf7); wr(7); wr(0xce); wr(0x8e); wr(14);
    zero_serial(); wr(0xc6); wr(0x46);
}
static int pair_id(unsigned first, unsigned second, unsigned value)
{
    unsigned attempt, i, n, hi, lo, port;
    for (attempt = 0; attempt < 2; ++attempt) {
        n = attempt ? 10 : 1;
        port = base + 1; dos_outb(base, first);
        for (i = 0; i < n; ++i) hi = dos_inb(port);
        dos_outb(base, second);
        for (i = 0; i < n; ++i) lo = dos_inb(port);
        if (((hi & 240) | (lo >> 4)) == value) return 1;
    }
    return 0;
}
static int scratch_trial(void)
{
    unsigned i, d, e, rd, re;
    for (i = 0; i < 100; ++i) {
        d = (i & 1) ? 10 : 5; e = 15 - d;
        changed(13,d); changed(14,e);
        rd = sample(13); re = sample(14);
        if (rd != d || re != e) return 0;
    }
    return 1;
}
static int calibrate(void)
{
    unsigned step, outer;
    wr(0xf6);
    for (outer = 0; outer < 2; ++outer) {
        hold = 128;
        for (step = 128; step; ) {
            if (scratch_trial()) { step >>= 1; hold -= step; }
            else { hold += step; step >>= 1; }
        }
        if (hold < 256) { hold += hold ? hold : 1; return 1; }
    }
    return 0;
}
static void socket_setup(void)
{
    serial_clock(0xf7); transfer(6); transfer(4);
    wr(7); wr(0xce); shift(0x80); wr(0x27); dos_wait_us(1000); wr(7); wr(0xa2);
}
static unsigned bus_read(void);

int pp_batch_start(unsigned char *startup, unsigned char *parallel)
{
    unsigned n, value = 0x31, sense = 0;
    unsigned pullup, pulldown;
    hold = 1;
    if (!startup) { hold = 2; goto configured; }
    if (!stream(startup) || !pair_id(6,5,0xf0)) goto unlink;
    reset_profile(0);
    if (!calibrate()) return 0;
    if (!stream(parallel) || !pair_id(15,12,7)) goto unlink;
    reset_profile(1); park_profile();
    /* The batch's explicit SET_ROM_TYPE re-loads the selected profile. */
    if (!stream(parallel) || !pair_id(15,12,7)) goto unlink;
    reset_profile(0); park_profile();
configured:
    if (!pair_id(15,12,7)) return 0;
    for (n = 0; n < 8; ++n) {
        unsigned bit = (value & 1) << 4;
        wr(0x85 | bit); wr(0xc5 | bit);
        sense |= ((sample(4) >> 3) & 1) << n;
        value >>= 1;
    }
    wr(5);
    /* 31h echo identifies revision 2, otherwise revision 1. This profile
       has minimum revision 0, so either answer is acceptable. */
    (void)sense;
    reset_profile(0); socket_setup();
    wr(0x26); wr(0xf0); wr(0xf1); wr(0x46); pullup = bus_read();
    wr(0x26); wr(0); wr(1); wr(0x46); pulldown = bus_read();
    if (pullup == 255 && pulldown == 0) { pp_batch_end(0); return 0; }
    return 1;
unlink:
    dos_outb(base, 0); dos_outb(base+2, 11);
    return 0;
}
static void address_cached(unsigned a)
{
    changed(2,a); changed(3,a >> 4); changed(13,a >> 8); changed(14,12 | ((a >> 12) & 3));
}
static unsigned bus_read(void)
{
    unsigned lo = sample(8);
    return lo | (sample(9) << 4);
}
static void end_socket(void)
{
    serial_clock(0xf7); changed(6,4); changed(2,0); changed(3,0); changed(13,0); changed(14,12);
    wr(0x8e); wr(14); zero_serial();
}
void pp_batch_end(int success)
{
    end_socket();
    if (success) { wr(0xc6); wr(0x46); }
}
/* Positive: readback matches; zero: retryable; negative: status fault. */
static int pulse(unsigned value, unsigned units)
{
    unsigned high = (latched[14] & 3) << 4;
    wr(0x26); changed(0,value); changed(1,value >> 4);
    wr(0x8e | high);
    while (units > 500) { dos_wait_us(50000); units -= 500; }
    dos_wait_us(units * 100);
    wr(0xce | high);
    if (sample(4) & 1) return -1;
    wr(0x46);
    return bus_read() == value;
}
/* 0 read, 1 verify, 2 write, 3 overwrite, 4 blank check. Report first error address. */
int pp_batch_transfer(unsigned char *buf, int mode, unsigned *where, unsigned start, unsigned length, int intelligent)
{
    int result;
    unsigned a, page, v, old, attempt, stop = start + length, limit;
    if (mode != 2) {
        for (a = start; a < stop; ++a) {
            *where = a; address_cached(a); old = bus_read();
            if (!mode) buf[a-start] = old;
            if (mode == 4 && old != 255) return 0;
            if (mode == 1 && old != buf[a-start]) return 0;
            if (mode == 3 && (old & buf[a-start]) != buf[a-start]) return -1;
        }
        if (mode != 3) return 1;
        end_socket(); socket_setup();
    }
    for (page = start; page < stop; page += 256) {
        /* 2.77 completes and verifies 256-byte blocks even when the
         * request ends halfway through one. The address on the programmer
         * bus is distinct from the eleven address pins of the adapter. */
        limit = page + (length < 256 ? length : 256);
        transfer(4); wr(0x47);
        for (a = page; a < limit; ++a) {
            *where = a; v = a < stop ? buf[a-start] : 255; address_cached(a); old = bus_read();
            if (old == v) continue;
            for (attempt = 0; attempt < 25; ++attempt) {
                result = pulse(v, intelligent ? 10 : 1);
                if (result) break;
            }
            if (result > 0 && intelligent) result = pulse(v,30*(attempt+1));
            if (result < 0) { wr(7); return 0; }
            if (!result) {
                unsigned prefix;
                wr(7); transfer(6);
                for (prefix = page; prefix < a; ++prefix) {
                    address_cached(prefix);
                    if (bus_read() != (prefix < stop ? buf[prefix-start] : 255)) { *where = prefix; break; }
                }
                return 0;
            }
        }
        wr(7); transfer(6);
        for (a = page; a < limit; ++a) {
            *where = a; address_cached(a);
            if (bus_read() != (a < stop ? buf[a-start] : 255)) return 0;
        }
    }
    return 1;
}
