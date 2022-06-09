"""Support for D-Link W215 smart switch."""
from __future__ import annotations

from datetime import timedelta
import logging
import urllib

from pyW215.pyW215 import SmartPlug
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_CONSUMPTION = "total_consumption"

CONF_USE_LEGACY_PROTOCOL = "use_legacy_protocol"

DEFAULT_NAME = "D-Link Smart Plug W215"
DEFAULT_PASSWORD = ""
DEFAULT_USERNAME = "admin"

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_USE_LEGACY_PROTOCOL, default=False): cv.boolean,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a D-Link Smart Plug."""

    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    use_legacy_protocol = config[CONF_USE_LEGACY_PROTOCOL]
    name = config[CONF_NAME]

    smartplug = SmartPlug(host, password, username, use_legacy_protocol)
    data = SmartPlugData(smartplug)

    add_entities([SmartPlugSwitch(hass, data, name)], True)


class SmartPlugSwitch(SwitchEntity):
    """Representation of a D-Link Smart Plug switch."""

    def __init__(self, hass, data, name):
        """Initialize the switch."""
        self.units = hass.config.units
        self.data = data
        self._name = name

    @property
    def name(self):
        """Return the name of the Smart Plug."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        try:
            ui_temp = self.units.temperature(int(self.data.temperature), TEMP_CELSIUS)
            temperature = ui_temp
        except (ValueError, TypeError):
            temperature = None

        try:
            total_consumption = float(self.data.total_consumption)
        except (ValueError, TypeError):
            total_consumption = None

        attrs = {
            ATTR_TOTAL_CONSUMPTION: total_consumption,
            ATTR_TEMPERATURE: temperature,
        }

        return attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.data.state == "ON"

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.data.smartplug.state = "ON"

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.data.smartplug.state = "OFF"

    def update(self):
        """Get the latest data from the smart plug and updates the states."""
        self.data.update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.data.available


class SmartPlugData:
    """Get the latest data from smart plug."""

    def __init__(self, smartplug):
        """Initialize the data object."""
        self.smartplug = smartplug
        self.state = None
        self.temperature = None
        self.current_consumption = None
        self.total_consumption = None
        self.available = False
        self._n_tried = 0
        self._last_tried = None

    def update(self):
        """Get the latest data from the smart plug."""
        if self._last_tried is not None:
            last_try_s = (dt_util.now() - self._last_tried).total_seconds() / 60
            retry_seconds = min(self._n_tried * 2, 10) - last_try_s
            if self._n_tried > 0 and retry_seconds > 0:
                _LOGGER.warning("Waiting %s s to retry", retry_seconds)
                return

        _state = "unknown"

        try:
            self._last_tried = dt_util.now()
            _state = self.smartplug.state
        except urllib.error.HTTPError:
            _LOGGER.error("D-Link connection problem")
        if _state == "unknown":
            self._n_tried += 1
            self.available = False
            _LOGGER.warning("Failed to connect to D-Link switch")
            return

        self.state = _state
        self.available = True

        self.temperature = self.smartplug.temperature
        self.current_consumption = self.smartplug.current_consumption
        self.total_consumption = self.smartplug.total_consumption
        self._n_tried = 0
