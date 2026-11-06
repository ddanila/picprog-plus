/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
#include <string.h>
#include "rf5_port.h"

static unsigned char image[RF5_SIZE];

/* Data is supplied by the user. Validate both slices before touching LPT. */
static unsigned char config[2][PP_STREAM_SIZE];
static int load_stream(FILE *f, unsigned char *buf, unsigned skip, unsigned long sum)
{
    unsigned i, bit;
    unsigned long crc = 0xffffffffUL;
    unsigned n;
    /* Sequential input also works with DOS libraries on either side of 64 KiB. */
    while (skip) {
        n = skip < PP_STREAM_SIZE ? skip : PP_STREAM_SIZE;
        if (fread(buf, 1, n, f) != n) return 0;
        skip -= n;
    }
    if (fread(buf, 1, PP_STREAM_SIZE, f) != PP_STREAM_SIZE) return 0;
    for (i = 0; i < PP_STREAM_SIZE; ++i) {
        crc ^= buf[i];
        for (bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320UL : 0UL);
    }
    return (crc ^ 0xffffffffUL) == sum;
}

int main(int argc, char **argv)
{
    unsigned port, a, old;
    int action, rc = 1;
    FILE *f;
    if (argc != 4 && argc != 5) goto usage;
    if (!strcmp(argv[1], "RRF5")) action = 0;
    else if (!strcmp(argv[1], "VRF5")) action = 1;
    else if (!strcmp(argv[1], "WRF5")) action = 2;
    else goto usage;
    if (!strcmp(argv[3], "378")) port = 0x378;
    else if (!strcmp(argv[3], "278")) port = 0x278;
    else if (!strcmp(argv[3], "3BC")) port = 0x3bc;
    else goto usage;

    f = fopen(argv[2], "rb");
    if (!action) {
        if (f) { fclose(f); puts("Read destination exists"); return 1; }
    } else {
        if (!f) { puts("Cannot open input"); return 1; }
        if (fread(image, 1, RF5_SIZE, f) != RF5_SIZE || getc(f) != EOF || ferror(f)) {
            fclose(f); puts("Expected exactly 2048 bytes"); return 1;
        }
        fclose(f);
    }
    if (argc == 5) {
        f = fopen(argv[4], "rb");
        if (!f) { puts("Cannot open configuration library"); return 1; }
        /* Parallel @64018, startup @69584: a 2788-byte gap. */
        rc = load_stream(f, config[1], 64018U, 0x7ce26b67UL) &&
             load_stream(f, config[0], 2788U, 0x4c53af75UL);
        fclose(f);
        if (!rc) { puts("Configuration payload mismatch"); return 1; }
        rc = 1;
    }
    pp_base(port);
    if (argc == 5 && !pp_configure(config[0], config[1])) {
        puts("Configuration or loopback failed"); return 1;
    }
    if (!pp_identify()) {
        puts("PicProg configured profile 07 not found"); return 1;
    }
    /* Preflight the entire part before the first programming pulse. */
    for (a = 0; a < RF5_SIZE; ++a) {
        old = pp_read(a);
        if (!action) image[a] = old;
        else if (action == 1 && old != image[a]) {
            printf("Verify mismatch %04X: expected %02X read %02X\n", a, image[a], old); goto done;
        } else if (action == 2 && (old & image[a]) != image[a]) {
            printf("Requires erase at %04X\n", a); goto done;
        }
    }
    if (action == 2) {
        for (a = 0; a < RF5_SIZE; ++a) {
            if (pp_read(a) == image[a]) continue;
            if (!pp_program(a, image[a]) || pp_read(a) != image[a]) {
                printf("Programming failed at %04X\n", a); goto done;
            }
        }
        /* Separate pass catches aliasing and corruption of earlier cells. */
        for (a = 0; a < RF5_SIZE; ++a) {
            if (pp_read(a) != image[a]) {
                printf("Final verification failed at %04X\n", a); goto done;
            }
        }
    }
    rc = 0;
done:
    pp_idle();
    if (!rc && !action) {
        f = fopen(argv[2], "wb");
        if (!f) return 1;
        if (fwrite(image, 1, RF5_SIZE, f) != RF5_SIZE) rc = 1;
        if (fflush(f) == EOF || ferror(f)) rc = 1;
        fclose(f);
        if (rc) puts("Writing output file failed");
    }
    if (!rc) printf("%s OK: 2048 bytes\n", argv[1]);
    return rc;
usage:
    puts("Usage: PICRF5 RRF5|VRF5|WRF5 image.bin 378|278|3BC [PICPROG.LIB]");
    return 2;
}
