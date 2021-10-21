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
    SelectDataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Add kostal plenticore Sensors."""
    plenticore = hass.data[DOMAIN][entry.entry_id]

    entities = []
    _LOGGER.debug("A %S", entry.entry_id)
    available_settings_data = await plenticore.client.get_settings()
    _LOGGER.debug("B %s", DOMAIN)
    select_data_update_coordinator = SelectDataUpdateCoordinator(
        hass,
        _LOGGER,
        "Select Data",
        timedelta(seconds=30),
        plenticore,
    )
    _LOGGER.debug("C")
    for module_id, name, options, is_on in SELECT_SETTINGS_DATA:
        _LOGGER.debug("D %s", name)
        if module_id not in available_settings_data:
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s", module_id, name
            )
            continue
        _LOGGER.debug("E %s", name)
        entities.append(
            PlenticoreDataSelect(
                coordinator=select_data_update_coordinator,
                entry_id=entry.entry_id,
                platform_name=entry.title,
                device_class='kostal_plenticore__battery',
                module_id=module_id,
                name=name,
                current_option='None',
                options=options,
                is_on=is_on,
                device_info=plenticore.device_info,
                unique_id=f"{entry.title}",
            )
        )
        _LOGGER.debug("F %s", select_data_update_coordinator)

    async_add_entities(entities)


class PlenticoreDataSelect(CoordinatorEntity, SelectEntity, ABC):
    """Representation of a Plenticore Switch."""

    def __init__(
        self,
        coordinator,
        entry_id: str,
        platform_name: str,
        device_class: str | None,
        module_id: str,
        name: str,
        current_option: str | None,
        options: list[str],
        is_on: str,
        device_info: DeviceInfo,
        unique_id: str,
    ):
        """Create a new switch Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self._attr_device_class = device_class
        self.module_id = module_id
        self._attr_current_option = current_option
        self._attr_options = options
        self.all_options = options
        self._is_on = is_on
        self._device_info = device_info
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        await super().async_will_remove_from_hass()

    async def get_currentoption(self) -> [str, bool]:
        """Get current option."""
        _LOGGER.debug("Get current option for %s", self.name)
        for all_option in self._attr_current_option:
            _LOGGER.debug("Get current option for %s for %s", self.name, all_option)
            if all_option != 'None':
                val = await self.async_read_data(self.module_id, all_option)
                if val:
                    return val

        return 'None'

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self.coordinator._attr_current_option = option
        for all_option in self._attr_options:
            if all_option != 'None':
                await self.coordinator.async_write_data(self.module_id, {all_option: "0"})
        _LOGGER.debug("Set current option for %s", option)
        await self.coordinator.async_write_data(self.module_id, {option: "1"})
        self.async_write_ha_state()



