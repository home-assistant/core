"""Platform for Kostal Plenticore switches."""
from __future__ import annotations

from abc import ABC
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SWITCH_SETTINGS_DATA
from .helper import SettingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Add kostal plenticore Switch."""
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
    for switch in SWITCH_SETTINGS_DATA:
        if switch.module_id not in available_settings_data or switch.data_id not in (
            setting.id for setting in available_settings_data[switch.module_id]
        ):
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s",
                switch.module_id,
                switch.data_id,
            )
            continue

        entities.append(
            PlenticoreDataSwitch(
                settings_data_update_coordinator,
                entry.entry_id,
                entry.title,
                switch.module_id,
                switch.data_id,
                switch.name,
                switch.is_on,
                switch.on_value,
                switch.on_label,
                switch.off_value,
                switch.off_label,
                plenticore.device_info,
                f"{entry.title} {switch.name}",
                f"{entry.entry_id}_{switch.module_id}_{switch.data_id}",
            )
        )

    async_add_entities(entities)


class PlenticoreDataSwitch(CoordinatorEntity, SwitchEntity, ABC):
    """Representation of a Plenticore Switch."""

    def __init__(
        self,
        coordinator,
        entry_id: str,
        platform_name: str,
        module_id: str,
        data_id: str,
        name: str,
        is_on: str,
        on_value: str,
        on_label: str,
        off_value: str,
        off_label: str,
        device_info: DeviceInfo,
        attr_name: str,
        attr_unique_id: str,
    ):
        """Create a new Switch Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = module_id
        self.data_id = data_id
        self._name = name
        self._is_on = is_on
        self._attr_name = attr_name
        self.on_value = on_value
        self.on_label = on_label
        self.off_value = off_value
        self.off_label = off_label
        self._attr_unique_id = attr_unique_id

        self._device_info = device_info

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
        self.coordinator.start_fetch_data(self.module_id, self.data_id)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if await self.coordinator.async_write_data(
            self.module_id, {self.data_id: self.on_value}
        ):
            self.coordinator.name = f"{self.platform_name} {self._name} {self.on_label}"
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn device off."""
        if await self.coordinator.async_write_data(
            self.module_id, {self.data_id: self.off_value}
        ):
            self.coordinator.name = (
                f"{self.platform_name} {self._name} {self.off_label}"
            )
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        if self.coordinator.data[self.module_id][self.data_id] == self._is_on:
            self.coordinator.name = f"{self.platform_name} {self._name} {self.on_label}"
        else:
            self.coordinator.name = (
                f"{self.platform_name} {self._name} {self.off_label}"
            )
        return bool(self.coordinator.data[self.module_id][self.data_id] == self._is_on)
