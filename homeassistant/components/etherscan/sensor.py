"""Support for Etherscan sensors."""

from __future__ import annotations

from datetime import timedelta

from pyetherscan import get_balance
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_ADDRESS, CONF_API_KEY, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_TOKEN_ADDRESS = "token_address"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
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
    api_key = config.get(CONF_API_KEY)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    token_address = config.get(CONF_TOKEN_ADDRESS)

    if token:
        token = token.upper()
        if not name:
            name = f"{token} Balance"
    if not name:
        name = "ETH Balance"

    add_entities([EtherscanSensor(address, api_key, name, token, token_address)], True)


class EtherscanSensor(SensorEntity):
    """Representation of an Etherscan.io sensor."""

    _attr_attribution = "Data provided by etherscan.io"

    def __init__(
        self,
        address: str,
        api_key: str,
        name: str | None,
        token: str | None,
        token_address: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._address = address
        self._api_key = api_key
        self._name = name
        self._token_address = token_address
        self._token = token
        self._state = None
        self._unit_of_measurement = self._token or "ETH"

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> float | str:
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Get the latest state of the sensor."""
        balance = get_balance(
            address=self._address,
            token=self._token_address or self._token,
            api_key=self._api_key,
        )
        self._state = balance if balance else str(balance)
