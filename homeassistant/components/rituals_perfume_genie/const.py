"""Constants for the Rituals Perfume Genie integration."""

from datetime import timedelta

DOMAIN = "rituals_perfume_genie"

# Old (API V1)
ACCOUNT_HASH = "account_hash"

# Rituals is strict about how often its API is used, and has blocked Home
# Assistant for polling too much before. One request fetches the state of
# all diffusers; the sensors are a request each, and change slowly.
UPDATE_INTERVAL = timedelta(minutes=5)
SENSORS_UPDATE_INTERVAL = timedelta(hours=1)

# The fill level changes over days, or suddenly when a cartridge is swapped,
# which the perfume sensor tells us. No need to ask for it every hour.
FILL_UPDATE_INTERVAL = timedelta(days=1)
