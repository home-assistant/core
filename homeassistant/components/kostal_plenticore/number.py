"""Platform for Kostal Plenticore numbers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pykoplenti import SettingsData

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SettingDataUpdateCoordinator
from .helper import PlenticoreDataFormatter

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PlenticoreNumberEntityDescription(NumberEntityDescription):
    """Describes a Plenticore number entity."""

    module_id: str
    data_id: str
    fmt_from: str
    fmt_to: str


NUMBER_SETTINGS_DATA = [
    PlenticoreNumberEntityDescription(
        key="battery_min_soc",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        icon="mdi:battery-negative",
        name="Battery min SoC",
        native_unit_of_measurement=PERCENTAGE,
        native_max_value=100,
        native_min_value=5,
        native_step=5,
        module_id="devices:local",
        data_id="Battery:MinSoc",
        fmt_from="format_round",
        fmt_to="format_round_back",
    ),
    PlenticoreNumberEntityDescription(
        key="battery_min_home_consumption",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        name="Battery min Home Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        native_max_value=38000,
        native_min_value=50,
        native_step=1,
        module_id="devices:local",
        data_id="Battery:MinHomeComsumption",
        fmt_from="format_round",
        fmt_to="format_round_back",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Kostal Plenticore Number entities."""
    plenticore = hass.data[DOMAIN][entry.entry_id]

    entities = []

    available_settings_data = await plenticore.client.get_settings()
    settings_data_update_coordinator = SettingDataUpdateCoordinator(
        hass, entry, _LOGGER, "Settings Data", timedelta(seconds=30), plenticore
    )

    for description in NUMBER_SETTINGS_DATA:
        if (
            description.module_id not in available_settings_data
            or description.data_id
            not in (
                setting.id for setting in available_settings_data[description.module_id]
            )
        ):
            _LOGGER.debug(
                "Skipping non existing setting data %s/%s",
                description.module_id,
                description.data_id,
            )
            continue

        setting_data = next(
            sd
            for sd in available_settings_data[description.module_id]
            if description.data_id == sd.id
        )

        entities.append(
            PlenticoreDataNumber(
                settings_data_update_coordinator,
                entry.entry_id,
                entry.title,
                plenticore.device_info,
                description,
                setting_data,
            )
        )

    async_add_entities(entities)


class PlenticoreDataNumber(
    CoordinatorEntity[SettingDataUpdateCoordinator], NumberEntity
):
    """Representation of a Kostal Plenticore Number entity."""

    entity_description: PlenticoreNumberEntityDescription

    def __init__(
        self,
        coordinator: SettingDataUpdateCoordinator,
        entry_id: str,
        platform_name: str,
        device_info: DeviceInfo,
        description: PlenticoreNumberEntityDescription,
        setting_data: SettingsData,
    ) -> None:
        """Initialize the Plenticore Number entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.entry_id = entry_id

        self._attr_device_info = device_info
        self._attr_unique_id = f"{self.entry_id}_{self.module_id}_{self.data_id}"
        self._attr_name = f"{platform_name} {description.name}"
        self._attr_mode = NumberMode.BOX

        self._formatter = PlenticoreDataFormatter.get_method(description.fmt_from)
        self._formatter_back = PlenticoreDataFormatter.get_method(description.fmt_to)

        # overwrite from retrieved setting data
        if setting_data.min is not None:
            self._attr_native_min_value = self._formatter(setting_data.min)
        if setting_data.max is not None:
            self._attr_native_max_value = self._formatter(setting_data.max)

    @property
    def module_id(self) -> str:
        """Return the plenticore module id of this entity."""
        return self.entity_description.module_id

    @property
    def data_id(self) -> str:
        """Return the plenticore data id for this entity."""
        return self.entity_description.data_id

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
        self.async_on_remove(
            self.coordinator.start_fetch_data(self.module_id, self.data_id)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id)
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.available:
            raw_value = self.coordinator.data[self.module_id][self.data_id]
            return self._formatter(raw_value)

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        str_value = self._formatter_back(value)
        await self.coordinator.async_write_data(
            self.module_id, {self.data_id: str_value}
        )
        await self.coordinator.async_refresh()
