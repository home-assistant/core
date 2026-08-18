"""BleBox switch implementation."""

from typing import Any, override

import blebox_uniapi.switch

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BleBoxConfigEntry
from .coordinator import BleBoxCoordinator
from .entity import BleBoxEntity
from .util import blebox_command

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox switch entity."""
    coordinator = config_entry.runtime_data
    entities = [
        BleBoxSwitchEntity(coordinator, feature)
        for feature in coordinator.box.features.get("switches", [])
    ]
    async_add_entities(entities)


class BleBoxSwitchEntity(BleBoxEntity[blebox_uniapi.switch.Switch], SwitchEntity):
    """Representation of a BleBox switch feature."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    _attr_name = None

    def __init__(
        self, coordinator: BleBoxCoordinator, feature: blebox_uniapi.switch.Switch
    ) -> None:
        """Initialize a BleBox switch feature."""
        super().__init__(coordinator, feature)
        if feature.name:
            self._attr_name = feature.name

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether switch is on."""
        return self._feature.is_on

    @blebox_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._feature.async_turn_on()

    @blebox_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._feature.async_turn_off()
