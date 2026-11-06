// SPDX-License-Identifier: GPL-2.0-only
// DOSBox-X Linux ppdev backend test double. Target is a regular file, never hardware.
#define _GNU_SOURCE
#include <errno.h>
#include <linux/ioctl.h>
#include <linux/ppdev.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

static struct stat target;
static int configured;
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
    case PPWCONTROL: control = *v; event = "WC"; break;
    case PPRCONTROL: *v = control; event = "RC"; break;
    case PPRSTATUS:
        *v = length[data] ? script[data][cursor[data]++ % length[data]] : replies[data];
        event = "RS"; break;
    default: fprintf(logfile, "UNKNOWN %lx\n", request); errno = ENOTTY; return -1;
    }
    fprintf(logfile, "%s %02x\n", event, *v);
    return 0;
}
