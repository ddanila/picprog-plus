/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
#include <string.h>
#include "rf5_port.h"

static unsigned char image[16384];

/* Data is supplied by the user. Validate all required slices before touching LPT. */
static unsigned char config[3][PP_STREAM_SIZE];
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

static int number(char *text, unsigned *result)
{
    unsigned value = 0;
    if (!*text) return 0;
    while (*text) {
        if (*text < '0' || *text > '9') return 0;
        if (value > 1638) return 0;
        value = value * 10 + (*text++ - '0');
        if (value > 16384) return 0;
    }
    *result = value;
    return 1;
}

/* Native 2716-family selections absent from the 2.77 catalog. Include
 * the DOS CP866 spellings, not UTF-8, in guest comparisons. */
static int unavailable(char *profile)
{
    static char *names[] = { "2716", "U2716C35", "RF2", "RF5", "K573RF2",
        "K573RF5", "\212573\220\2242", "\212573\220\2245", "\220\2242", "\220\2245", 0 };
    unsigned i,n;
    for (i=0; names[i]; ++i) {
        n = strlen(names[i]);
        if (!strncmp(profile,names[i],n) &&
            (!strcmp(profile+n,",I") || !strcmp(profile+n,",Q"))) return 1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    unsigned capacity = 8192, port, a, start = 0, length = RF5_SIZE;
    int action, rc = 1, batch = 0, intelligent = 0, selection = 1;
    FILE *f;
    if (argc == 8) {
        if (!strcmp(argv[7],"AT28C16,P")) { selection=2; capacity=2048; }
        else if (!strcmp(argv[7],"DEFAULT")) selection = 0;
        else if (unavailable(argv[7])) selection = -1;
        else if (!strcmp(argv[7],"27C128,I") || !strcmp(argv[7],"27C128,Q")) capacity = 16384;
        else if (strcmp(argv[7],"27C64,I") && strcmp(argv[7],"27C64,Q")) goto usage;
        intelligent = argv[7][strlen(argv[7])-1] == 'I';
        --argc;
    }
    if (argc != 4 && argc != 5 && argc != 7) goto usage;
    if (!strcmp(argv[1], "RRF5")) action = 0;
    else if (!strcmp(argv[1], "VRF5")) action = 1;
    else if (!strcmp(argv[1], "WRF5")) action = 3;
    else if (argc >= 5 && !strcmp(argv[1], "CHECK")) { batch = 1; action = 4; }
    else if (argc >= 5 && !strcmp(argv[1], "READ")) { batch = 1; action = 0; }
    else if (argc >= 5 && !strcmp(argv[1], "VERIFY")) { batch = 1; action = 1; }
    else if (argc >= 5 && !strcmp(argv[1], "WRITE")) { batch = 1; action = 2; }
    else if (argc >= 5 && !strcmp(argv[1], "OVERWRITE")) { batch = 1; action = 3; }
    else goto usage;
    if (argc == 7 && (!batch || !number(argv[5], &start) || !number(argv[6], &length) ||
                      !length || (selection != 0 && start + length > capacity))) goto usage;
    if (!selection && start + length > RF5_SIZE) selection = -2;
    if (!strcmp(argv[3], "378")) port = 0x378;
    else if (!strcmp(argv[3], "278")) port = 0x278;
    else if (!strcmp(argv[3], "3BC")) port = 0x3bc;
    else goto usage;

    if (selection >= 0) {
        f = action == 4 ? NULL : fopen(argv[2], "rb");
        if (!action) {
            if (f) { fclose(f); puts("Read destination exists"); return 1; }
        } else if (action != 4) {
            if (!f) { puts("Cannot open input"); return 1; }
            if (fread(image, 1, length, f) != length || getc(f) != EOF || ferror(f)) {
                fclose(f); printf("Expected exactly %u bytes\n",length); return 1;
            }
            fclose(f);
        }
    }
    if (argc >= 5) {
        f = fopen(argv[4], "rb");
        if (!f) { puts("Cannot open configuration library"); return 1; }
        /* Parallel @64018, startup @69584: a 2788-byte gap. */
        rc = (selection != 2 || load_stream(f, config[2], 19490U, 0x6670671eUL)) &&
             load_stream(f, config[1], selection == 2 ? 41750U : 64018U, 0x7ce26b67UL) &&
             load_stream(f, config[0], 2788U, 0x4c53af75UL);
        fclose(f);
        if (!rc) { puts("Configuration payload mismatch"); return 1; }
        rc = 1;
    }
    pp_base(port);
    if (!pp_batch_start(argc >= 5 ? config[0] : NULL,
                        argc >= 5 ? config[1] : NULL, selection, config[2])) {
        puts("Configuration, ID or socket check failed"); return 1;
    }
    if (selection < 0) {
        puts(selection == -2 ? "PROM address outside default range" : "Invalid ROM type (PicProg 2.77)");
        return 1;
    }
    rc = pp_batch_transfer(image, action, &a, start, length, intelligent);
    pp_batch_end(rc == 1);
    if (rc < 0) printf("Requires erase at %04X\n", a);
    else if (!rc) printf("%s at %04X\n", action == 1 ? "Verify mismatch" : "Operation failed", a);
    rc = rc != 1;
    if (!rc && !action) {
        f = fopen(argv[2], "wb");
        if (!f) return 1;
        if (fwrite(image, 1, length, f) != length) rc = 1;
        if (fflush(f) == EOF || ferror(f)) rc = 1;
        fclose(f);
        if (rc) puts("Writing output file failed");
    }
    if (!rc) printf("%s OK: %u bytes\n", argv[1], length);
    return rc;
usage:
    puts("Usage: PICRF5 RRF5|VRF5|WRF5 image.bin 378|278|3BC [PICPROG.LIB]");
    puts("       PICRF5 READ|VERIFY|WRITE|OVERWRITE|CHECK image.bin base PICPROG.LIB [start length [profile]]");
    return 2;
}
