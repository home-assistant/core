"""Support for number entities through the SmartThings cloud API."""

from __future__ import annotations

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add number entities for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsWasherRinseCyclesNumberEntity(entry_data.client, device)
        for device in entry_data.devices.values()
        if Capability.CUSTOM_WASHER_RINSE_CYCLES in device.status[MAIN]
    )


class SmartThingsWasherRinseCyclesNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_translation_key = "washer_rinse_cycles"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.BOX

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the instance."""
        super().__init__(client, device, {Capability.CUSTOM_WASHER_RINSE_CYCLES})
        self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{Capability.CUSTOM_WASHER_RINSE_CYCLES}_{Attribute.WASHER_RINSE_CYCLES}_{Attribute.WASHER_RINSE_CYCLES}"

    @property
    def options(self) -> list[int]:
        """Return the list of options."""
        values = self.get_attribute_value(
            Capability.CUSTOM_WASHER_RINSE_CYCLES,
            Attribute.SUPPORTED_WASHER_RINSE_CYCLES,
        )
        return [int(value) for value in values] if values else []

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.CUSTOM_WASHER_RINSE_CYCLES, Attribute.WASHER_RINSE_CYCLES
            )
        )

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return min(self.options)

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return max(self.options)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.CUSTOM_WASHER_RINSE_CYCLES,
            Command.SET_WASHER_RINSE_CYCLES,
            str(int(value)),
        )
