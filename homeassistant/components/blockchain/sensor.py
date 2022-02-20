"""Support for Blockchain.com sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyblockchain import get_balance, validate_address
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by blockchain.com"

CONF_ADDRESSES = "addresses"

DEFAULT_NAME = "Bitcoin Balance"

ICON = "mdi:currency-btc"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESSES): [cv.string],
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Blockchain.com sensors."""

    addresses = config[CONF_ADDRESSES]
    name = config[CONF_NAME]

    for address in addresses:
        if not validate_address(address):
            _LOGGER.error("Bitcoin address is not valid: %s", address)
            return

    add_entities([BlockchainSensor(name, addresses)], True)


class BlockchainSensor(SensorEntity):
    """Representation of a Blockchain.com sensor."""

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
    _attr_icon = ICON
    _attr_native_unit_of_measurement = "BTC"

    def __init__(self, name, addresses):
        """Initialize the sensor."""
        self._attr_name = name
        self.addresses = addresses

    def update(self):
        """Get the latest state of the sensor."""
        self._attr_native_value = get_balance(self.addresses)
