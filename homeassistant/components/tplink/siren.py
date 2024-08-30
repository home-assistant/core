"""Support for TPLink hub alarm."""

from __future__ import annotations

from typing import Any

from kasa import Device, Module

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import CoordinatedTPLinkEntity, async_refresh_after


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up siren entities."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    if Module.Alarm in device.modules:
        async_add_entities([TPLinkSirenEntity(device, parent_coordinator)])


class TPLinkSirenEntity(CoordinatedTPLinkEntity, SirenEntity):
    """Representation of a tplink hub alarm."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
    ) -> None:
        """Initialize the siren entity."""
        self._test_alarm = device.features["test_alarm"]
        self._stop_alarm = device.features["stop_alarm"]
        self._alarm_active = device.features["alarm"]

        super().__init__(device, coordinator)

    @async_refresh_after
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on."""
        await self._test_alarm.set_value(True)

    @async_refresh_after
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self._stop_alarm.set_value(True)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._alarm_active.value

    def _get_unique_id(self) -> str:
        """Return unique id."""
        return f"{self._device.device_id}_siren"
