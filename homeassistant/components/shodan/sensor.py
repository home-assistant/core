"""Sensor for displaying information from Shodan.io."""

from __future__ import annotations

import contextlib
from datetime import timedelta
import ipaddress
import logging

import requests
import shodan
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_QUERY = "query"
CONF_IP_NAME = "ip_name"
CONF_PORT_NAME = "port_name"
CONF_IP = "ip"
CONF_SELF_IDENT = "self_identify"

DEFAULT_NAME = "Shodan Sensor"
DEFAULT_IP_NAME = "Shodan IP Sensor"
DEFAULT_PORT_NAME = "Shodan Port Sensor"

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_QUERY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_IP_NAME, default=DEFAULT_IP_NAME): cv.string,
        vol.Optional(CONF_PORT_NAME, default=DEFAULT_PORT_NAME): cv.string,
        vol.Optional(CONF_IP): cv.string,
        vol.Optional(CONF_SELF_IDENT): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Shodan sensor."""
    api_key = config[CONF_API_KEY]
    query = ""
    valid_ip = ""

    try:
        config[CONF_IP]
        try:
            valid_ip = str(ipaddress.ip_address(config[CONF_IP]))
            ip = config[CONF_IP]
        except ValueError as ve:
            _LOGGER.warning("IP Address is invalid: %s", ve)
            return
    except KeyError:
        pass

    try:
        config[CONF_SELF_IDENT]
        try:
            ip = requests.get("https://checkip.amazonaws.com", timeout=5).text.strip()
            valid_ip = str(ip)
        except requests.exceptions.RequestException as error:
            _LOGGER.warning("Issue connecting to checkip.amazonaws.com: %s", error)
            return
    except KeyError:
        pass

    if valid_ip:
        ip_information = ShodanIP(shodan.Shodan(api_key), ip)
        try:
            ip_information.update()
        except shodan.exception.APIError as error:
            _LOGGER.warning("Unable to connect to Shodan.io: %s", error)
            return

        ip_name = config[CONF_IP_NAME]
        port_name = config[CONF_PORT_NAME]
        add_entities([ShodanIPSensor(ip_information, ip_name)], True)
        add_entities([ShodanPortSensor(ip_information, port_name)], True)

    with contextlib.suppress(KeyError):
        query = config[CONF_QUERY]

    if query:
        data = ShodanData(shodan.Shodan(api_key), query)
        try:
            data.update()
        except shodan.exception.APIError as error:
            _LOGGER.warning("Unable to connect to Shodan.io: %s", error)
            return

        name = config[CONF_NAME]
        add_entities([ShodanSensor(data, name)], True)


class ShodanSensor(SensorEntity):
    """Representation of the Shodan sensor."""

    _attr_attribution = "Data provided by Shodan"
    _attr_icon = "mdi:tooltip-text"
    _attr_native_unit_of_measurement = "Hits"

    def __init__(self, data: ShodanData, name: str) -> None:
        """Initialize the Shodan sensor."""
        self.data = data
        self._attr_name = name

    def update(self) -> None:
        """Get the latest data and updates the states."""
        data = self.data.update()
        self._attr_native_value = data["total"]


class ShodanIPSensor(SensorEntity):
    """Representation of the Shodan IP Sensor."""

    _attr_attribution = "Data provided by Shodan"
    _attr_icon = "mdi:tooltip-text"

    def __init__(self, ip_info: ShodanIP, name: str) -> None:
        """Initialize the Shodan IP sensor."""
        self.ip_info = ip_info
        self._attr_name = name

    def update(self) -> None:
        """Get the latest IP Info and update the states."""
        ip_info = self.ip_info.update()
        self._attr_native_value = ip_info["ip_str"]


class ShodanPortSensor(SensorEntity):
    """Representation of the Shodan Port Sensor."""

    _attr_attribution = "Data provided by Shodan"
    _attr_icon = "mdi:tooltip-text"

    def __init__(self, ip_info: ShodanIP, name: str) -> None:
        """Initialize the Shodan Port sensor."""
        self.ip_info = ip_info
        self._attr_name = name

    def update(self) -> None:
        """Get the latest Port Info and update the states."""
        ip_info = self.ip_info.update()
        self._attr_native_value = ip_info["ports"]


class ShodanData:
    """Get the latest data and update the states."""

    def __init__(self, api: shodan.Shodan, query: str) -> None:
        """Initialize the data object."""
        self._api = api
        self._query = query

    def update(self):
        """Get the latest data from shodan.io."""
        return self._api.count(self._query)


class ShodanIP:
    """Get information about the IP."""

    def __init__(self, api: shodan.Shodan, ip: str) -> None:
        """Initialize the IP object."""
        self._api = api
        self._ip = ip

    def update(self):
        """Get the latest IP Info from shodan.io."""
        return self._api.host(self._ip, minify=True)
