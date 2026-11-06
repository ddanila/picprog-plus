/* SPDX-License-Identifier: GPL-2.0-only */
#define RF5_SIZE 2048
void pp_base(unsigned port);
int pp_identify(void);
void pp_idle(void);
unsigned pp_read(unsigned address);
int pp_program(unsigned address, unsigned value);
int pp_configure(unsigned char *startup, unsigned char *parallel);
#define PP_STREAM_SIZE 2778
