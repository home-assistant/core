"""BleBox switch implementation."""
from datetime import timedelta
from typing import Any

import blebox_uniapi.switch

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, get_blebox_features

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox switch entity."""
    entities: list[BleBoxSwitchEntity] = []

    for feature in get_blebox_features(hass, config_entry, "switches"):
        entities.append(BleBoxSwitchEntity(feature))

    async_add_entities(entities, True)


class BleBoxSwitchEntity(BleBoxEntity[blebox_uniapi.switch.Switch], SwitchEntity):
    """Representation of a BleBox switch feature."""

    def __init__(self, feature: blebox_uniapi.switch.Switch) -> None:
        """Initialize a BleBox switch feature."""
        super().__init__(feature)
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self):
        """Return whether switch is on."""
        return self._feature.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._feature.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._feature.async_turn_off()
