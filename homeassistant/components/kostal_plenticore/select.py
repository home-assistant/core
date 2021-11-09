"""Select Kostal Plenticore charging/usage mode"""
from __future__ import annotations

import json
from abc import ABC
from datetime import timedelta
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant, callback
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
    available_settings_data = await plenticore.client.get_settings()
    select_data_update_coordinator = SelectDataUpdateCoordinator(
        hass,
        _LOGGER,
        "Select Data",
        timedelta(seconds=30),
        plenticore,
    )
    for module_id, data_id, name, options, is_on in SELECT_SETTINGS_DATA:
        if module_id not in available_settings_data:
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s", module_id, name
            )
            continue
        entities.append(
            PlenticoreDataSelect(
                coordinator=select_data_update_coordinator,
                entry_id=entry.entry_id,
                platform_name=entry.title,
                device_class='kostal_plenticore__battery',
                module_id=module_id,
                data_id=data_id,
                name=name,
                current_option='None',
                options=options,
                is_on=is_on,
                device_info=plenticore.device_info,
                unique_id=f"{entry.entry_id}_{module_id}",
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
        device_class: str | None,
        module_id: str,
        data_id: str,
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
        self.data_id = data_id
        self._attr_options = options
        self.all_options = options
        self._attr_current_option = current_option
        self._is_on = is_on
        self._device_info = device_info
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id

        self.async_update_callback()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # self._attr_current_option = self.coordinator.data[self.module_id][self.data_id]
        is_available = (
            super().available
            and self.coordinator.data is not None
            and self.module_id in self.coordinator.data
            and self.data_id in self.coordinator.data[self.module_id]
        )

        if is_available:
            _LOGGER.debug("--------------------aaaaaa------------------------------------ %s",
                          json.dumps(self.coordinator.data[self.module_id][self.data_id]))
            self._attr_current_option = self.coordinator.data[self.module_id][self.data_id]

        return is_available

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.coordinator.start_fetch_data(self.module_id, self.data_id, self.all_options)
        self.async_update_callback()

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        _LOGGER.debug("option is %s", option)
        self._attr_current_option = option
        for all_option in self._attr_options:
            if all_option != 'None':
                _LOGGER.debug("Set select to 0 for %s", all_option)
                await self.coordinator.async_write_data(self.module_id, {all_option: "0"})
        if option != 'None':
            _LOGGER.debug("Set select to 1 for %s", option)
            await self.coordinator.async_write_data(self.module_id, {option: "1"})
        self.async_write_ha_state()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        _LOGGER.debug("--------------------ccccccc------------------------------------")
        self._attr_current_option = 'None'

