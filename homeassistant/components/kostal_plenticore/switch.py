"""Platform for Kostal Plenticore switches."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .helper import SettingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class PlenticoreRequiredKeysMixin:
    """A class that describes required properties for plenticore switch entities."""

    module_id: str
    is_on: str
    on_value: str
    on_label: str
    off_value: str
    off_label: str


@dataclass
class PlenticoreSwitchEntityDescription(
    SwitchEntityDescription, PlenticoreRequiredKeysMixin
):
    """A class that describes plenticore switch entities."""


SWITCH_SETTINGS_DATA = [
    PlenticoreSwitchEntityDescription(
        module_id="devices:local",
        key="Battery:Strategy",
        name="Battery Strategy",
        is_on="1",
        on_value="1",
        on_label="Automatic",
        off_value="2",
        off_label="Automatic economical",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
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
    for description in SWITCH_SETTINGS_DATA:
        if (
            description.module_id not in available_settings_data
            or description.key
            not in (
                setting.id for setting in available_settings_data[description.module_id]
            )
        ):
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s",
                description.module_id,
                description.key,
            )
            continue

        entities.append(
            PlenticoreDataSwitch(
                settings_data_update_coordinator,
                description,
                entry.entry_id,
                entry.title,
                plenticore.device_info,
            )
        )

    async_add_entities(entities)


class PlenticoreDataSwitch(
    CoordinatorEntity[SettingDataUpdateCoordinator], SwitchEntity
):
    """Representation of a Plenticore Switch."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: PlenticoreSwitchEntityDescription

    def __init__(
        self,
        coordinator: SettingDataUpdateCoordinator,
        description: PlenticoreSwitchEntityDescription,
        entry_id: str,
        platform_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Create a new Switch Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = description.module_id
        self.data_id = description.key
        self._name = description.name
        self._is_on = description.is_on
        self._attr_name = f"{platform_name} {description.name}"
        self.on_value = description.on_value
        self.on_label = description.on_label
        self.off_value = description.off_value
        self.off_label = description.off_label
        self._attr_unique_id = f"{entry_id}_{description.module_id}_{description.key}"

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if await self.coordinator.async_write_data(
            self.module_id, {self.data_id: self.on_value}
        ):
            self.coordinator.name = f"{self.platform_name} {self._name} {self.on_label}"
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
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
