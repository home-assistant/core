from datetime import timedelta

from homeassistant.const import Platform

DOMAIN="kindhome_solarbeaker"
PLATFORMS = [Platform.COVER]

UPDATE_INTERVAL = timedelta(seconds=20)

SERVICE_UUID = "75c276c3-8f97-20bc-a143-b354244886d4"
TITLE="Kindhome Solarbeaker"

DATA_DEVICE = "device"
DATA_COOR = "coordinator"
