"""Constants for the Aqara integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.const import Platform

DOMAIN = "aqara"
LOGGER = logging.getLogger(__package__)

CONF_COUNTRY_CODE = "country_code"

AQARA_BATTERY_LOW_ENTITY_NEW = "aqara_battery_entity_new"
AQARA_DISCOVERY_NEW = "aqara_discovery_new"
AQARA_HA_SIGNAL_UPDATE_ENTITY = "aqara_entry_update"
AQARA_HA_SIGNAL_UPDATE_POINT_VALUE = "aqara_point_update"
AQARA_HA_SIGNAL_REGISTER_POINT = "aqara_register_point"


PLATFORMS = [
    Platform.BINARY_SENSOR,
]


class AqaraCloudOpenAPIEndpoint:
    """Aqara Cloud Open API Endpoint."""

    CHINA = "https://open-cn.aqara.com"
    AMERICA = "https://open-usa.aqara.com"
    COREA = "https://open-kr.aqara.com"
    RUSSIA = "https://open-ru.aqara.com"
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
