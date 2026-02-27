"""Fan platform for Sharp COCORO Air."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharpCocoroAirConfigEntry
from .const import DISPLAY_TO_API_MODE, OPERATION_MODES
from .coordinator import SharpCocoroAirCoordinator
from .entity import SharpCocoroAirEntity

PARALLEL_UPDATES = 0
PRESET_MODES = list(OPERATION_MODES.keys())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharpCocoroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sharp fan entities."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set(coordinator.data)
    async_add_entities(
        SharpAirPurifierFan(coordinator, device_id) for device_id in known_devices
    )

    @callback
    def _async_add_new_devices() -> None:
        """Add fan entities for newly discovered devices."""
        new_device_ids = set(coordinator.data) - known_devices
        if new_device_ids:
            known_devices.update(new_device_ids)
            async_add_entities(
                SharpAirPurifierFan(coordinator, device_id)
                for device_id in new_device_ids
            )

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class SharpAirPurifierFan(SharpCocoroAirEntity, FanEntity):
    """Fan entity representing a Sharp air purifier."""

    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )
    _attr_translation_key = "air_purifier"

    def __init__(
        self,
        coordinator: SharpCocoroAirCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_fan"

    @property
    def is_on(self) -> bool | None:
        """Return true if the device is on."""
        power = self.device_properties.power
        if power is None:
            return None
        return power == "on"

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        mode_display = self.device_properties.operation_mode
        if mode_display is None:
            return None
        return DISPLAY_TO_API_MODE.get(mode_display, mode_display.lower())

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        return PRESET_MODES

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_power_on(device)
        if preset_mode is not None:
            await self.coordinator.async_set_mode(device, preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_power_off(device)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode."""
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_set_mode(device, preset_mode)
