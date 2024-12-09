"""Binary sensor platform for solmate_mocks integration."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the binary sensor platform."""
    _LOGGER.info("Setting up binary sensor platform")
    async_add_entities([MockFastChargeButton()])


class MockFastChargeButton(BinarySensorEntity):
    """Binary sensor for mocking fast charge button."""

    _attr_name = "Mock Fast Charge Button"
    _attr_unique_id = "mock_fast_charge_button"
    # _attr_device_class = BinarySensorDeviceClass

    def __init__(self) -> None:
        """Initialize the binary sensor."""
        self._attr_is_on = False
