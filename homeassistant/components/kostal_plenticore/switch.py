"""Platform for Kostal Plenticore switches."""
from __future__ import annotations

from abc import ABC
from datetime import timedelta
import logging
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SWITCH_SETTINGS_DATA,
)
from .helper import (
    PlenticoreDataFormatter,
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
    for module_id, data_id, name, sensor_data, fmt in SWITCH_SETTINGS_DATA:
        if module_id not in available_settings_data or data_id not in (
                setting.id for setting in available_settings_data[module_id]
        ):
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s", module_id, data_id
            )
            continue

        entities.append(
            PlenticoreDataSwitch(
                settings_data_update_coordinator,
                entry.entry_id,
                entry.title,
                module_id,
                data_id,
                name,
                sensor_data,
                PlenticoreDataFormatter.get_method(fmt),
                plenticore.device_info,
                f"{entry.title} {name}",
                f"{entry.entry_id}_{module_id}_{data_id}",
            )
        )

    async_add_entities(entities)


class PlenticoreDataSwitch(CoordinatorEntity, SwitchEntity, ABC):
    def __init__(
            self,
            coordinator,
            entry_id: str,
            platform_name: str,
            module_id: str,
            data_id: str,
            switch_name: str,
            switch_data: dict[str, Any],
            formatter: Callable[[str], Any],
            device_info: DeviceInfo,
            attr_name: str,
            attr_unique_id: str,
    ):
        """Create a new switch Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = module_id
        self.data_id = data_id
        self._state: bool | None = None
        self._last_run_success: bool | None = None
        self._switch_name = switch_name
        self._switch_data = switch_data
        self._formatter = formatter
        self._attr_name = attr_name
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

    async def async_turn_on(self) -> None:
        """Turn device on."""
        if await self.coordinator._async_write_data(self.module_id, {self.data_id: '1'}):
            self._state = True
            self._last_run_success = True
            await self.coordinator.async_request_refresh()
        else:
            self._last_run_success = False

    async def async_turn_off(self) -> None:
        """Turn device off."""
        if await self.coordinator._async_write_data(self.module_id, {self.data_id: '0'}):
            self._state = False
            self._last_run_success = True
            await self.coordinator.async_request_refresh()
        else:
            self._last_run_success = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self._state)

    @property
    def icon(self) -> str | None:
        """Return the icon name of this switch Entity or None."""
        return self._switch_data.get(ATTR_ICON)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success}