"""Platform for Kostal Plenticore select widgets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PlenticoreConfigEntry, SelectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PlenticoreSelectEntityDescription(SelectEntityDescription):
    """A class that describes plenticore select entities."""

    module_id: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlenticoreConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add kostal plenticore Select widget."""
    plenticore = entry.runtime_data

    available_settings_data = await plenticore.client.get_settings()
    select_data_update_coordinator = SelectDataUpdateCoordinator(
        hass, entry, _LOGGER, "Settings Data", timedelta(seconds=30), plenticore
    )

    entities = []

    # Add option for battery mode selection
    if (
        device_local_data_ids := available_settings_data.get("devices:local")
    ) is not None:
        options = ["None"]

        if any(
            setting.id == "Battery:SmartBatteryControl:Enable"
            for setting in device_local_data_ids
        ):
            options.append("Battery:SmartBatteryControl:Enable")

        if any(
            setting.id == "Battery:TimeControl:Enable"
            for setting in device_local_data_ids
        ):
            options.append("Battery:TimeControl:Enable")

        battery_mode_settings = await plenticore.client.get_setting_values(
            "devices:local",
            (
                "Battery:Type",
                "EnergySensor:SensorPosition",
                "EnergySensor:InstalledSensor",
            ),
        )

        try:
            sensor_position = int(
                battery_mode_settings["devices:local"]["EnergySensor:SensorPosition"]
            )
            battery_type = int(battery_mode_settings["devices:local"]["Battery:Type"])
            installed_sensor = int(
                battery_mode_settings["devices:local"]["EnergySensor:InstalledSensor"]
            )
        except ValueError:
            _LOGGER.warning(
                "Failed to retrieve battery mode settings: %s", battery_mode_settings
            )
        else:
            if sensor_position == 2 and battery_type > 0 and installed_sensor > 0:
                # This option is only available if
                # - energy sensor is installed
                # - energy sensor is positioned at the grid connection
                # - a battery is installed
                # It is added to this selection because it is mutually exclusive to the other modes
                # and only one of these modes can be active at a time.
                options.append("EnergyMgmt:AcStorage")
            else:
                _LOGGER.debug(
                    "Skipping excess energy switch, not supported (Sensor position: %d, Battery type: %d, Installed sensor: %d)",
                    sensor_position,
                    battery_type,
                    installed_sensor,
                )

        if len(options) > 1:
            entities.append(
                PlenticoreDataSelect(
                    select_data_update_coordinator,
                    PlenticoreSelectEntityDescription(
                        module_id="devices:local",
                        key="battery_charge",
                        name="Battery Charging / Usage mode",
                        options=options,
                    ),
                    entry_id=entry.entry_id,
                    platform_name=entry.title,
                    device_info=plenticore.device_info,
                )
            )

    async_add_entities(entities)


class PlenticoreDataSelect(
    CoordinatorEntity[SelectDataUpdateCoordinator], SelectEntity
):
    """Representation of a Plenticore Select."""

    _attr_entity_category = EntityCategory.CONFIG
    entity_description: PlenticoreSelectEntityDescription

    def __init__(
        self,
        coordinator: SelectDataUpdateCoordinator,
        description: PlenticoreSelectEntityDescription,
        entry_id: str,
        platform_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Create a new Select Entity for Plenticore process data."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entry_id = entry_id
        self.platform_name = platform_name
        self.module_id = description.module_id
        self.data_id = description.key
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_{description.module_id}"

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
            self.coordinator.start_fetch_data(
                self.module_id, self.data_id, self.options
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister this entity from the Update Coordinator."""
        self.coordinator.stop_fetch_data(self.module_id, self.data_id, self.options)
        await super().async_will_remove_from_hass()

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        for all_option in self.options:
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
