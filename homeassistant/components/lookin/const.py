"""The lookin integration constants."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN = "lookin"

INFO_URL: Final = "http://{host}/device"
METEO_SENSOR_URL: Final = "http://{host}/sensors/meteo"
DEVICES_INFO_URL: Final = "http://{host}/data"
DEVICE_INFO_URL: Final = "http://{host}/data/{uuid}"
UPDATE_CLIMATE_URL: Final = "http://{host}/commands/ir/ac/{extra}{status}"
SEND_IR_COMMAND: Final = "http://{host}/commands/ir/localremote/{uuid}{command}{signal}"

LOGGER = logging.getLogger(__name__)

DEVICES: Final = "devices"
LOOKIN_DEVICE: Final = "lookin_device"
PROTOCOL: Final = "protocol"
METEO_COORDINATOR: Final = "meteo_coordinator"

PLATFORMS: Final = ["sensor", "climate", "media_player", "light", "vacuum", "fan"]


POWER_CMD: Final = "power"
POWER_ON_CMD: Final = "power_on"
POWER_OFF_CMD: Final = "power_off"
