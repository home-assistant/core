"""Platform for Kostal Plenticore select widgets."""
from __future__ import annotations

from abc import ABC
from datetime import timedelta
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SELECT_SETTINGS_DATA
from .helper import Plenticore, SelectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add kostal plenticore Select widget."""
    plenticore: Plenticore = hass.data[DOMAIN][entry.entry_id]
    select_data_update_coordinator = SelectDataUpdateCoordinator(
        hass,
        _LOGGER,
        "Settings Data",
        timedelta(seconds=30),
        plenticore,
    )

    async_add_entities(
        PlenticoreDataSelect(
            select_data_update_coordinator,
            entry_id=entry.entry_id,
            platform_name=entry.title,
            device_class="kostal_plenticore__battery",
            module_id=select.module_id,
            data_id=select.data_id,
            name=select.name,
            current_option="None",
            options=select.options,
            is_on=select.is_on,
            device_info=plenticore.device_info,
            unique_id=f"{entry.entry_id}_{select.module_id}",
        )
        for select in SELECT_SETTINGS_DATA
    )


class PlenticoreDataSelect(CoordinatorEntity, SelectEntity, ABC):
    """Representation of a Plenticore Select."""

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
    ) -> None:
        """Create a new Select Entity for Plenticore process data."""
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.module_id in self.coordinator.data
            and self.data_id in self.coordinator.data[self.module_id]
        )

    async def async_added_to_hass(self) -> None:
        """Register this entity on the Update Coordinator."""
        await super().async_added_to_hass()
        self.coordinator.start_fetch_data(
            self.module_id, self.data_id, self.all_options
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id, self.all_options)
        await super().async_will_remove_from_hass()

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self._attr_current_option = option
        for all_option in self._attr_options:
            if all_option != "None":
                await self.coordinator.async_write_data(
                    self.module_id, {all_option: "0"}
                )
        if option != "None":
            await self.coordinator.async_write_data(self.module_id, {option: "1"})
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if self.available:
            return self.coordinator.data[self.module_id][self.data_id]

        return None
