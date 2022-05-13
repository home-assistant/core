"""Constants for the Aqara integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from homeassistant.const import Platform

DOMAIN = "aqara"
LOGGER = logging.getLogger(__package__)

CONF_AUTH_TYPE = "auth_type"
CONF_ENDPOINT = "endpoint"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_APP_TYPE = "aqara_app_type"

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
    Platform.BINARY_SENSOR,
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
