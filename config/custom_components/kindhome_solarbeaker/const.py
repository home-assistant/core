from datetime import timedelta

from homeassistant.const import Platform

DOMAIN="kindhome_solarbeaker"
PLATFORMS = [Platform.COVER]

UPDATE_INTERVAL = timedelta(seconds=20)

DATA_DEVICE = "device"
DATA_COOR = "coordinator"
