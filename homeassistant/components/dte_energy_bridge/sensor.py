"""Support for monitoring energy usage using the DTE energy bridge."""
from __future__ import annotations

from http import HTTPStatus
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, POWER_KILO_WATT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_IP_ADDRESS = "ip"
CONF_VERSION = "version"

DEFAULT_NAME = "Current Energy Usage"
DEFAULT_VERSION = 1

ICON = "mdi:flash"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.All(
            vol.Coerce(int), vol.Any(1, 2)
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the DTE energy bridge sensor."""
    name = config[CONF_NAME]
    ip_address = config[CONF_IP_ADDRESS]
    version = config[CONF_VERSION]

    add_entities([DteEnergyBridgeSensor(ip_address, name, version)], True)


class DteEnergyBridgeSensor(SensorEntity):
    """Implementation of the DTE Energy Bridge sensors."""

    _attr_icon = ICON
    _attr_native_unit_of_measurement = POWER_KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, ip_address, name, version):
        """Initialize the sensor."""
        self._version = version

        if self._version == 1:
            self._url = f"http://{ip_address}/instantaneousdemand"
        elif self._version == 2:
            self._url = f"http://{ip_address}:8888/zigbee/se/instantaneousdemand"

        self._attr_name = name

    def update(self):
        """Get the energy usage data from the DTE energy bridge."""
        try:
            response = requests.get(self._url, timeout=5)
        except (requests.exceptions.RequestException, ValueError):
            _LOGGER.warning(
                "Could not update status for DTE Energy Bridge (%s)", self._attr_name
            )
            return

        if response.status_code != HTTPStatus.OK:
            _LOGGER.warning(
                "Invalid status_code from DTE Energy Bridge: %s (%s)",
                response.status_code,
                self._attr_name,
            )
            return

        response_split = response.text.split()

        if len(response_split) != 2:
            _LOGGER.warning(
                'Invalid response from DTE Energy Bridge: "%s" (%s)',
                response.text,
                self._attr_name,
            )
            return

        val = float(response_split[0])

        # A workaround for a bug in the DTE energy bridge.
        # The returned value can randomly be in W or kW.  Checking for a
        # a decimal seems to be a reliable way to determine the units.
        # Limiting to version 1 because version 2 apparently always returns
        # values in the format 000000.000 kW, but the scaling is Watts
        # NOT kWatts
        if self._version == 1 and "." in response_split[0]:
            self._attr_native_value = val
        else:
            self._attr_native_value = val / 1000
