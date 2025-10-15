"""Support for OctoPrint number entities."""

from __future__ import annotations

import logging

from pyoctoprintapi import OctoprintClient

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OctoprintDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def is_bed(tool_name: str) -> bool:
    """Return True if the tool name indicates a bed."""
    return tool_name == "bed"

def is_extruder(tool_name: str) -> bool:
    """Return True if the tool name indicates an extruder."""
    return tool_name.startswith("tool") and tool_name[4:].isdigit()

def is_first_extruder(tool_name: str) -> bool:
    """Return True if the tool name indicates the first extruder."""
    return tool_name == "tool0"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OctoPrint number entities."""
    coordinator: OctoprintDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]["coordinator"]
    client: OctoprintClient = hass.data[DOMAIN][config_entry.entry_id]["client"]
    device_id = config_entry.unique_id

    assert device_id is not None

    known_tools = set()

    @callback
    def async_add_tool_numbers() -> None:
        if not coordinator.data["printer"]:
            return

        new_numbers: list[OctoPrintTemperatureNumber] = []
        for tool in coordinator.data["printer"].temperatures:
            if (
                is_extruder(tool.name) or is_bed(tool.name)
            ) and tool.name not in known_tools:
                assert device_id is not None
                known_tools.add(tool.name)
                new_numbers.append(
                    OctoPrintTemperatureNumber(
                        coordinator,
                        client,
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
    """Representation of an OctoPrint temperature setter entity."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_device_class = NumberDeviceClass.TEMPERATURE

    def __init__(
        self,
        coordinator: OctoprintDataUpdateCoordinator,
        client: OctoprintClient,
        tool: str,
        device_id: str,
    ) -> None:
        """Initialize a new OctoPrint temperature number entity."""
        super().__init__(coordinator)
        self._api_tool = tool
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{device_id}_{tool}_temperature"
        self._client = client
        self._device_id = device_id
        if is_bed(tool):
            self._attr_translation_key = "bed_temperature"
        elif is_first_extruder(tool):
            self._attr_translation_key = "extruder_temperature"
        else:
            self._attr_translation_key = "extruder_n_temperature"
            self._attr_translation_placeholders = {"n": tool[4:]}

    @property
    def native_value(self) -> float | None:
        """Return the current target temperature."""
        if not self.coordinator.data["printer"]:
            return None
        for tool in self.coordinator.data["printer"].temperatures:
            if tool.name == self._api_tool and tool.target_temp is not None:
                return tool.target_temp

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the target temperature."""

        try:
            if is_bed(self._api_tool):
                await self._client.set_bed_temperature(int(value))
            elif is_extruder(self._api_tool):
                await self._client.set_tool_temperature(self._api_tool, int(value))
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_setting_temperature",
                translation_placeholders={
                    "tool": self._api_tool,
                },
            ) from err

        # Request coordinator update to reflect the change
        await self.coordinator.async_request_refresh()
