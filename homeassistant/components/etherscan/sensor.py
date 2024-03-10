"""Support for Etherscan sensors."""

from __future__ import annotations

from datetime import timedelta

from pyetherscan import get_balance
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_TOKEN_ADDRESS = "token_address"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_TOKEN_ADDRESS): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Etherscan.io sensors."""
    address = config.get(CONF_ADDRESS)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    token_address = config.get(CONF_TOKEN_ADDRESS)

    if token:
        token = token.upper()
        if not name:
            name = f"{token} Balance"
    if not name:
        name = "ETH Balance"

    add_entities([EtherscanSensor(name, address, token, token_address)], True)


class EtherscanSensor(SensorEntity):
    """Representation of an Etherscan.io sensor."""

    _attr_attribution = "Data provided by etherscan.io"

    def __init__(self, name, address, token, token_address):
        """Initialize the sensor."""
        self._name = name
        self._address = address
        self._token_address = token_address
        self._token = token
        self._state = None
        self._unit_of_measurement = self._token or "ETH"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Get the latest state of the sensor."""

        if self._token_address:
            self._state = get_balance(self._address, self._token_address)
        elif self._token:
            self._state = get_balance(self._address, self._token)
        else:
            self._state = get_balance(self._address)
