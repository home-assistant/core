"""Constants for the Vacmaster Cardio54 integration."""

from typing import Final

from rf_protocols import ModulationType

DOMAIN: Final = "vacmaster_cardio54"

CONF_TRANSMITTER: Final = "transmitter"
CONF_DEVICE_ID: Final = "device_id"

FREQUENCY: Final = 433_920_000
MODULATION: Final = ModulationType.OOK

# EV1527 time base. 4 x 330 us = 1320 us, which is the symbol period measured on
# the original Cardio54 remote (short pulse ~320 us, long pulse ~1000 us).
TIMEBASE_US: Final = 330

# 20-bit EV1527 device ID space; a fresh ID is generated per config entry.
DEVICE_ID_BITS: Final = 20

SPEED_COUNT: Final = 3

# EV1527 data nibbles. EV1527Command encodes the 4-bit data LSB-first on the
# wire, so the integers here are the bit-reversed forms of the captured frames:
# the Cardio54 transmits (MSB-first on wire) Power=0001, speed I=1000,
# speed II=0100, speed III=0010, which give the LSB-first ints 8, 1, 2, 4.
DATA_POWER: Final = 8
DATA_SPEEDS: Final = (1, 2, 4)

# rf_protocols repeat_count is the number of *additional* transmissions.
FRAME_REPEATS: Final = 10
# ~80 frames is a ~3.4 s burst, long enough for the 5 s pairing window.
PAIR_FRAME_REPEATS: Final = 80
