"""Constants used by Speedtest.net."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Final

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND, TIME_MILLISECONDS

DOMAIN: Final = "speedtestdotnet"

SPEED_TEST_SERVICE: Final = "speedtest"


@dataclass
class SpeedtestSensorEntityDescription(SensorEntityDescription):
    """Class describing Speedtest sensor entities."""

    value: Callable = round


SENSOR_TYPES: Final[tuple[SpeedtestSensorEntityDescription, ...]] = (
    SpeedtestSensorEntityDescription(
        key="ping",
        name="Ping",
        native_unit_of_measurement=TIME_MILLISECONDS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SpeedtestSensorEntityDescription(
        key="download",
        name="Download",
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda value: round(value / 10 ** 6, 2),
    ),
    SpeedtestSensorEntityDescription(
        key="upload",
        name="Upload",
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda value: round(value / 10 ** 6, 2),
    ),
)

CONF_SERVER_NAME: Final = "server_name"
CONF_SERVER_ID: Final = "server_id"
CONF_MANUAL: Final = "manual"

ATTR_BYTES_RECEIVED: Final = "bytes_received"
ATTR_BYTES_SENT: Final = "bytes_sent"
ATTR_SERVER_COUNTRY: Final = "server_country"
ATTR_SERVER_ID: Final = "server_id"
ATTR_SERVER_NAME: Final = "server_name"


DEFAULT_NAME: Final = "SpeedTest"
DEFAULT_SCAN_INTERVAL: Final = 60
DEFAULT_SERVER: Final = "*Auto Detect"

ATTRIBUTION: Final = "Data retrieved from Speedtest.net by Ookla"

ICON: Final = "mdi:speedometer"

PLATFORMS: Final = ["sensor"]
