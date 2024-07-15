"""Constants for the Weheat integration."""

from logging import Logger, getLogger

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower

DOMAIN = "weheat"

OAUTH2_AUTHORIZE = (
    "https://auth.early.weheat.nl/auth/realms/Weheat/protocol/openid-connect/auth/"
)
OAUTH2_TOKEN = (
    "https://auth.early.weheat.nl/auth/realms/Weheat/protocol/openid-connect/token/"
)

API_URL = "https://api.early.weheat.nl"

UPDATE_INTERVAL = 10


LOGGER: Logger = getLogger(__package__)

SENSORS = [
    SensorEntityDescription(
        name="Output power",
        key="power_output",
        icon="mdi:heat-wave",
        # native_unit_of_measurement="W",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        name="Input power",
        key="power_input",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        name="COP",
        key="cop",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]
