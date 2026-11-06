// SPDX-License-Identifier: GPL-2.0-only
// К573РФ5 digital socket model. A program event describes one complete CS
// pulse with address/data held stable; no analog ramp or cell wear model.
#ifndef PP_RF5_CHIP_H
#define PP_RF5_CHIP_H

#include <stdbool.h>
#include <stdint.h>

enum { RF5_BYTES = 2048, RF5_PROGRAM_US = 50000 };

static inline unsigned rf5_address(unsigned pins) { return pins & (RF5_BYTES - 1); }

// False means high impedance; the caller models the rest of the bus.
static inline bool rf5_read(const uint8_t *cell, unsigned pins, bool cs_high,
                            bool oe_high, uint8_t *out) {
    if (cs_high || oe_high) return false;
    *out = cell[rf5_address(pins)];
    return true;
}

static inline bool rf5_program_pulse(uint8_t *cell, unsigned pins, uint8_t data,
                                     bool vpp_program, bool oe_high, unsigned high_us) {
    if (!vpp_program || !oe_high || high_us < RF5_PROGRAM_US) return false;
    cell[rf5_address(pins)] &= data;
    return true;
}
#endif
