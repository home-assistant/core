"""Select Kostal Plenticore charging/usage mode"""
from __future__ import annotations

from abc import ABC
from datetime import timedelta
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SELECT_SETTINGS_DATA,
)
from .helper import (
    SettingDataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Add kostal plenticore Sensors."""
    plenticore = hass.data[DOMAIN][entry.entry_id]

    entities = []

    available_settings_data = await plenticore.client.get_settings()
    settings_data_update_coordinator = SettingDataUpdateCoordinator(
        hass,
        _LOGGER,
        "Settings Data",
        timedelta(seconds=30),
        plenticore,
    )
    for module_id, name, options in SELECT_SETTINGS_DATA:
        entities.append(
            PlenticoreDataSelect(
                settings_data_update_coordinator,
                entry.entry_id,
                entry.title,
                module_id,
                'None',
                options,
                plenticore.device_info,
                f"{entry.title}",
                f"{entry.entry_id}",
            )
        )

    async_add_entities(entities)


class PlenticoreDataSelect(CoordinatorEntity, SelectEntity, ABC):
    """Representation of a Plenticore Switch."""

    def __init__(
        self,
        coordinator,
        entry_id: str,
        platform_name: str,
        module_id: str,
        current_option: str | None,
        options: list[str],
        name: str,
        unique_id: str,
    ):
        """Create a new switch Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = module_id
        self._attr_current_option = current_option
        self.attr_options = options
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.module_id in self.coordinator.data
        )

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.coordinator.get_currentoption(self.module_id, self.attr_options)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        await super().async_will_remove_from_hass()

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self.coordinator._attr_current_option = option
        for all_option in self._select_options:
            if all_option != 'None' :
                self.coordinator.async_write_data(self.module_id, {all_option: "0"})
        self.coordinator.async_write_data(self.module_id, {option: "1"})
        self.coordinator.async_write_ha_state()



