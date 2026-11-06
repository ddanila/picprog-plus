/* SPDX-License-Identifier: GPL-2.0-only */
#define RF5_SIZE 2048
void pp_base(unsigned port);
#define PP_STREAM_SIZE 2778
int pp_batch_start(unsigned char *startup, unsigned char *parallel);
int pp_batch_transfer(unsigned char *buf, int mode, unsigned *where, unsigned start, unsigned length, int intelligent);
void pp_batch_end(int success);
