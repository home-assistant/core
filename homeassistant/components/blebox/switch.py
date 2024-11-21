"""BleBox switch implementation."""

from datetime import timedelta
from typing import Any

import blebox_uniapi.switch

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxConfigEntry
from .entity import BleBoxEntity

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox switch entity."""
    entities = [
        BleBoxSwitchEntity(feature)
        for feature in config_entry.runtime_data.features.get("switches", [])
    ]
    async_add_entities(entities, True)


class BleBoxSwitchEntity(BleBoxEntity[blebox_uniapi.switch.Switch], SwitchEntity):
    """Representation of a BleBox switch feature."""

    _attr_device_class = SwitchDeviceClass.SWITCH

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
