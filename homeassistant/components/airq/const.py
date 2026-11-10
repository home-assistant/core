"""Constants for the air-Q integration."""

from typing import Final

CONF_RETURN_AVERAGE: Final = "return_average"
CONF_CLIP_NEGATIVE: Final = "clip_negatives"
DOMAIN: Final = "airq"
MANUFACTURER: Final = "CorantGmbH"
ACTIVITY_BECQUEREL_PER_CUBIC_METER: Final = "Bq/m³"
LENGTH_MICROMETER: Final = "μm"
# The device reports the size-resolved particle counts in the native unit of its
# optical counter: the number of particles per 100 mL (0.1 L) of sampled air.
PARTICLE_COUNT_PER_100_MILLILITER: Final = "particles/100mL"
UPDATE_INTERVAL: float = 10.0
