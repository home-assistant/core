"""Support for OctoPrint number entities."""

from __future__ import annotations

import logging

from pyoctoprintapi import OctoprintClient, OctoprintPrinterInfo

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator, async_get_client_for_service_call
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OctoPrint number entities."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    device_id = config_entry.unique_id

    assert device_id is not None

    known_tools = set()

    @callback
    def async_add_tool_numbers() -> None:
        if not coordinator.data["printer"]:
            return

        new_numbers: list[OctoPrintTemperatureNumber] = []
        for tool in [
            tool
            for tool in coordinator.data["printer"].temperatures
            if tool.name not in known_tools
        ]:
            assert device_id is not None
            known_tools.add(tool.name)
            new_numbers.append(
                OctoPrintTemperatureNumber(
                    coordinator,
                    tool.name,
                    device_id,
                )
            )
        async_add_entities(new_numbers)

    config_entry.async_on_unload(coordinator.async_add_listener(async_add_tool_numbers))

    if coordinator.data["printer"]:
        async_add_tool_numbers()


class OctoPrintTemperatureNumber(
    CoordinatorEntity[OctoprintDataUpdateCoordinator], NumberEntity
):
    """Representation of an OctoPrint temperature number entity."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        tool: str,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint temperature number entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._api_tool = tool
        self._attr_name = f"OctoPrint set {tool} temperature"
        self._attr_unique_id = f"set-{tool}-temp-{device_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        printer: OctoprintPrinterInfo = self.coordinator.data["printer"]
        if not printer:
            return None

        for temp in printer.temperatures:
            if temp.name == self._api_tool:
                if temp.target_temp is None:
                    return None
                return round(temp.target_temp, 2)

        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data["printer"]

    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""
        client: OctoprintClient = self.hass.data[DOMAIN][
            self.coordinator.config_entry.entry_id
        ]["client"]

        if self._api_tool.lower() == "bed":
            await client.set_bed_temperature(value)
        elif self._api_tool.startswith("tool"):
            await client.set_tool_temperature(self._api_tool, value)

        # Request coordinator update to reflect the change
        await self.coordinator.async_request_refresh()