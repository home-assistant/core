"""Constants for the Aqara integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

# from aqara_iot import AqaraCloudOpenAPIEndpoint

# from homeassistant.components.sensor import SensorDeviceClass
# from homeassistant.const import (
#     CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
#     CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
#     CONCENTRATION_PARTS_PER_BILLION,
#     CONCENTRATION_PARTS_PER_MILLION,
#     ELECTRIC_CURRENT_AMPERE,
#     ELECTRIC_CURRENT_MILLIAMPERE,
#     ELECTRIC_POTENTIAL_MILLIVOLT,
#     ELECTRIC_POTENTIAL_VOLT,
#     ENERGY_KILO_WATT_HOUR,
#     ENERGY_WATT_HOUR,
#     LIGHT_LUX,
#     PERCENTAGE,
#     POWER_KILO_WATT,
#     POWER_WATT,
#     PRESSURE_BAR,
#     PRESSURE_HPA,
#     PRESSURE_INHG,
#     PRESSURE_MBAR,
#     PRESSURE_PA,
#     PRESSURE_PSI,
#     SIGNAL_STRENGTH_DECIBELS,
#     SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
#     TEMP_CELSIUS,
#     TEMP_FAHRENHEIT,
#     VOLUME_CUBIC_FEET,
#     VOLUME_CUBIC_METERS,
# )

DOMAIN = "aqara"
LOGGER = logging.getLogger(__package__)

CONF_AUTH_TYPE = "auth_type"
CONF_PROJECT_TYPE = "aqara_project_type"
CONF_ENDPOINT = "endpoint"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_APP_TYPE = "aqara_app_type"

# DEVICE_CLASS_AQARA_BASIC_ANTI_FLICKR = "aqara__basic_anti_flickr"
# DEVICE_CLASS_AQARA_BASIC_NIGHTVISION = "aqara__basic_nightvision"
# DEVICE_CLASS_AQARA_DECIBEL_SENSITIVITY = "aqara__decibel_sensitivity"
# DEVICE_CLASS_AQARA_IPC_WORK_MODE = "aqara__ipc_work_mode"
# DEVICE_CLASS_AQARA_LED_TYPE = "aqara__led_type"
# DEVICE_CLASS_AQARA_LIGHT_MODE = "aqara__light_mode"
# DEVICE_CLASS_AQARA_MOTION_SENSITIVITY = "aqara__motion_sensitivity"
# DEVICE_CLASS_AQARA_RECORD_MODE = "aqara__record_mode"
# DEVICE_CLASS_AQARA_RELAY_STATUS = "aqara__relay_status"
# DEVICE_CLASS_AQARA_STATUS = "aqara__status"
# DEVICE_CLASS_AQARA_FINGERBOT_MODE = "aqara__fingerbot_mode"
# DEVICE_CLASS_AQARA_VACUUM_CISTERN = "aqara__vacuum_cistern"
# DEVICE_CLASS_AQARA_VACUUM_COLLECTION = "aqara__vacuum_collection"
# DEVICE_CLASS_AQARA_VACUUM_MODE = "aqara__vacuum_mode"

AQARA_BATTERY_LOW_ENTITY_NEW = "aqara_battery_entity_new"
AQARA_DISCOVERY_NEW = "aqara_discovery_new"
AQARA_HA_SIGNAL_UPDATE_ENTITY = "aqara_entry_update"
AQARA_HA_SIGNAL_UPDATE_POINT_VALUE = "aqara_point_update"
AQARA_HA_SIGNAL_REGISTER_POINT = "aqara_register_point"

AQARA_RESPONSE_CODE = "code"
AQARA_RESPONSE_RESULT = "result"
AQARA_RESPONSE_MSG = "msg"
AQARA_RESPONSE_SUCCESS = "success"
AQARA_RESPONSE_PLATFORM_URL = "platform_url"

EMPTY_UNIT = "  "

PLATFORMS = [
    "binary_sensor",
    "button",
    # "camera",
    "climate",
    "cover",
    # "fan",
    # "humidifier",
    "light",
    "number",
    "scene",
    "select",
    "sensor",
    "siren",
    "switch",
    # "vacuum",
    # "lock",
]


class WorkMode(str, Enum):
    """Work modes."""

    COLOUR = "colour"
    MUSIC = "music"
    SCENE = "scene"
    WHITE = "white"


@dataclass
class UnitOfMeasurement:
    """Describes a unit of measurement."""

    unit: str
    device_classes: set[str]

    aliases: set[str] = field(default_factory=set)
    conversion_unit: str | None = None
    conversion_fn: Callable[[float], float] | None = None


class AqaraCloudOpenAPIEndpoint:
    """Aqara Cloud Open API Endpoint."""

    # "/v3.0/open/api"

    #
    CHINA = "https://open-cn.aqara.com"
    # CHINA = "https://developer-test.aqara.com"

    #
    AMERICA = "https://open-usa.aqara.com"

    #
    COREA = "https://open-kr.aqara.com"

    #
    RUSSIA = "https://open-ru.aqara.com"

    #
    EUROPE = "https://open-ger.aqara.com"


@dataclass
class Country:
    """Describe a supported country."""

    name: str
    country_code: str
    endpoint: str = AqaraCloudOpenAPIEndpoint.EUROPE


AQARA_COUNTRIES = [
    Country("China", "86", AqaraCloudOpenAPIEndpoint.CHINA),
    Country("Europe", "251", AqaraCloudOpenAPIEndpoint.EUROPE),
    Country("South Korea", "850", AqaraCloudOpenAPIEndpoint.COREA),
    Country("Russia", "7", AqaraCloudOpenAPIEndpoint.RUSSIA),
    Country("United States", "1", AqaraCloudOpenAPIEndpoint.AMERICA),
]
