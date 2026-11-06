// SPDX-License-Identifier: GPL-2.0-only
// DOSBox-X Linux ppdev backend test double. Target is a regular file, never hardware.
#define _GNU_SOURCE
#include "rf5_chip.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <linux/ioctl.h>
#include <linux/ppdev.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

static struct stat target;
static int configured, echo_de;
static unsigned char scratch[2];
static unsigned char *chip, reg[16];
static unsigned capacity;
static int pulse_fault, empty_socket;
static int device_phase;
static unsigned drop_pulses; /* Optional fault injection; counts qualified pulses only. */
static unsigned address(void) {
    return reg[2] | (reg[3] << 4) | (reg[13] << 8) | ((reg[14] & 3) << 12);
}
static void latch(unsigned char bus) {
    unsigned index = bus & 15, value = bus >> 4;
    if (chip && device_phase && index == 14 && (reg[14] & 12) == 8 && (value & 12) == 12 && (reg[14] & 3) == (value & 3) &&
        reg[7] == 4 && reg[6] == 2) {
        // The virtual adapter supplies a nominal RF5 pulse. The DOS
        // transport profile's real socket voltages/timing are not reused.
        if (pulse_fault) { /* Hardware status fault, no successful pulse. */ }
        else if (drop_pulses) --drop_pulses;
        else if (capacity > RF5_BYTES) chip[address() & (capacity-1)] &= reg[0] | (reg[1] << 4);
        else rf5_program_pulse(chip, address(), reg[0] | (reg[1] << 4), true, true, RF5_PROGRAM_US);
    }
    reg[index] = value;
}
static unsigned char data, control, replies[256];
static unsigned char script[256][256];
static unsigned length[256], cursor[256];
static FILE *logfile;

__attribute__((constructor)) static void setup(void) {
    const char *path = getenv("PP_ENDPOINT"), *log = getenv("PP_TRACE");
    if (!path || stat(path, &target) || !S_ISREG(target.st_mode) || !log) return;
    logfile = fopen(log, "w");
    if (!logfile) return;
    setvbuf(logfile, NULL, _IOLBF, 0);
    unsigned initial = getenv("PP_STATUS") ? strtoul(getenv("PP_STATUS"), NULL, 0) : 0xd8;
    for (unsigned i=0; i<256; ++i) replies[i] = initial;
    const char *map = getenv("PP_MAP");
    while (map && *map) {
        unsigned key, value; int used;
        if (sscanf(map, "%x%n", &key, &used) != 1 || key > 255 || map[used] != ':')
            goto invalid;
        map += used + 1;
        length[key] = 0;
        do {
            if (sscanf(map, "%x%n", &value, &used) != 1 || value > 255 || length[key] == 256)
                goto invalid;
            script[key][length[key]++] = value;
            map += used;
            if (*map != '/') break;
            ++map;
        } while (1);
        if (!*map) break;
        if (*map++ != ',' || !*map) goto invalid;
    }
    echo_de = getenv("PP_ECHO_DE") && atoi(getenv("PP_ECHO_DE"));
    const char *image = getenv("PP_RF5_IMAGE");
    if (image && *image) {
        int fd = open(image, O_RDWR | O_NOFOLLOW);
        struct stat st;
        if (fd < 0 || fstat(fd, &st) || !S_ISREG(st.st_mode) || (st.st_size != RF5_BYTES && st.st_size != 8192 && st.st_size != 16384) ||
            (chip = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0)) == MAP_FAILED) {
            fprintf(stderr, "RF5 requires a writable regular 2048-, 8192- or 16384-byte image\n"); _exit(2);
        }
        capacity = st.st_size;
        close(fd);
    }
    empty_socket = getenv("PP_EMPTY_SOCKET") && atoi(getenv("PP_EMPTY_SOCKET"));
    pulse_fault = getenv("PP_PULSE_FAULT") && atoi(getenv("PP_PULSE_FAULT"));
    if (getenv("PP_DROP_PULSES")) drop_pulses = strtoul(getenv("PP_DROP_PULSES"), NULL, 10);
    configured = 1;
    return;
invalid:
    fprintf(stderr, "Invalid PP_MAP near %s\n", map); _exit(2);
}

// Linux syscall ABI: forward the third machine word unchanged for other ioctls.
int ioctl(int fd, unsigned long request, unsigned long arg) {
    struct stat sb;
    if (!configured || _IOC_TYPE(request) != PP_IOCTL || fstat(fd,&sb) ||
        sb.st_dev != target.st_dev || sb.st_ino != target.st_ino)
        return syscall(SYS_ioctl, fd, request, arg);
    unsigned char *v = (void *)arg;
    const char *event;
    switch (request) {
    case PPCLAIM: case PPRELEASE: case PPSETMODE: return 0;
    case PPDATADIR: fprintf(logfile, "DIR %d\n", *(int *)arg); return 0;
    case PPWDATA: data = *v; event = "WD"; break;
    case PPRDATA: *v = data; event = "RD"; break;
    case PPWCONTROL:
        if (*v == 5 && control != 5) latch(data);
        if (echo_de && *v == 5 && control != 5 &&
            ((data & 15) == 13 || (data & 15) == 14))
            scratch[(data & 15) - 13] = data & 0xf0;
        control = *v; event = "WC"; break;
    case PPRCONTROL: *v = control; event = "RC"; break;
    case PPRSTATUS:
        *v = length[data] ? script[data][cursor[data]++ % length[data]] : replies[data];
        if (echo_de && (data == 13 || data == 14))
            *v = (*v & 15) | scratch[data - 13];
        if (chip) {
            if (data == 15) device_phase = 1;
            if (device_phase && data == 4 && reg[7] == 4)
                *v = (*v & ~0x10) | (pulse_fault ? 0x10 : 0);
            if (device_phase && (data == 8 || data == 9)) {
                uint8_t byte = 0xff;
                if (empty_socket) byte = reg[0] | (reg[1] << 4);
                else if (capacity > RF5_BYTES && reg[6] == 4) byte = chip[address() & (capacity-1)];
                else rf5_read(chip, address(), false, reg[6] != 4, &byte);
                *v = (*v & 15) | (data == 8 ? (byte << 4) & 240 : byte & 240);
            }
        }
        event = "RS"; break;
    default: fprintf(logfile, "UNKNOWN %lx\n", request); errno = ENOTTY; return -1;
    }
    fprintf(logfile, "%s %02x\n", event, *v);
    return 0;
}
