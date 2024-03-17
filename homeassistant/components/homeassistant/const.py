"""Constants for the Homeassistant integration."""

from typing import Final

import homeassistant.core as ha

DOMAIN = ha.DOMAIN

DATA_EXPOSED_ENTITIES = f"{DOMAIN}.exposed_entites"
DATA_STOP_HANDLER = f"{DOMAIN}.stop_handler"

SERVICE_HOMEASSISTANT_STOP: Final = "stop"
SERVICE_HOMEASSISTANT_RESTART: Final = "restart"
