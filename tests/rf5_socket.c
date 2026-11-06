// SPDX-License-Identifier: GPL-2.0-only
#include "../tools/rf5_chip.h"
#include <assert.h>
#include <string.h>

int main(void) {
    uint8_t chip[RF5_BYTES], bus = 0x39;
    memset(chip, 0xff, sizeof chip);
    assert(!rf5_program_pulse(chip, 2047, 0, false, true, 50000));
    assert(!rf5_program_pulse(chip, 2047, 0, true, false, 50000));
    assert(!rf5_program_pulse(chip, 2047, 0, true, true, 1));
    assert(chip[2047] == 0xff);
    assert(rf5_program_pulse(chip, 2047, 0xa5, true, true, 50000));
    assert(rf5_program_pulse(chip, 2047, 0x5f, true, true, 50000));
    assert(!rf5_read(chip, 2047, true, false, &bus) && bus == 0x39);
    assert(!rf5_read(chip, 2047, false, true, &bus) && bus == 0x39);
    assert(rf5_read(chip, 2047, false, false, &bus) && bus == 0x05);
    assert(chip[0] == 0xff && chip[2046] == 0xff);
    return 0;
}
