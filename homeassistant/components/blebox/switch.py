"""BleBox switch implementation."""
from datetime import timedelta

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities
from .const import BLEBOX_TO_HASS_DEVICE_CLASSES

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox switch entity."""
    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxSwitchEntity, "switches"
    )


class BleBoxSwitchEntity(BleBoxEntity, SwitchEntity):
    """Representation of a BleBox switch feature."""

    def __init__(self, feature):
        """Initialize a BleBox switch feature."""
        super().__init__(feature)
        self._attr_device_class = BLEBOX_TO_HASS_DEVICE_CLASSES[feature.device_class]

    @property
    def is_on(self):
        """Return whether switch is on."""
        return self._feature.is_on

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        await self._feature.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        await self._feature.async_turn_off()
