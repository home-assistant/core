"""Binary Sensor platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain
from typing import cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TeslemetryConfigEntry
from .const import TeslemetryState
from .entity import (
    TeslemetryEnergyInfoEntity,
    TeslemetryEnergyLiveEntity,
    TeslemetryVehicleEntity,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TeslemetryBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Teslemetry binary sensor entity."""

    is_on: Callable[[StateType], bool] = bool


VEHICLE_DESCRIPTIONS: tuple[TeslemetryBinarySensorEntityDescription, ...] = (
    TeslemetryBinarySensorEntityDescription(
        key="state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on=lambda x: x == TeslemetryState.ONLINE,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_battery_heater_on",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_charger_phases",
        is_on=lambda x: cast(int, x) > 1,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_preconditioning_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="climate_state_is_preconditioning",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_scheduled_charging_pending",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_trip_charging",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_conn_charge_cable",
        is_on=lambda x: x != "<invalid>",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="climate_state_cabin_overheat_protection_actively_cooling",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_dashcam_state",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on=lambda x: x == "Recording",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_is_user_present",
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_fl",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_fr",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_rl",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_rr",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_fd_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_fp_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_rd_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_rp_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_df",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_dr",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_pf",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_pr",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENERGY_LIVE_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(key="backup_capable"),
    BinarySensorEntityDescription(key="grid_services_active"),
)


ENERGY_INFO_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="components_grid_services_enabled",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry binary sensor platform from a config entry."""

    async_add_entities(
        chain(
            (  # Vehicles
                TeslemetryVehicleBinarySensorEntity(vehicle, description)
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (  # Energy Site Live
                TeslemetryEnergyLiveBinarySensorEntity(energysite, description)
                for energysite in entry.runtime_data.energysites
                for description in ENERGY_LIVE_DESCRIPTIONS
                if energysite.info_coordinator.data.get("components_battery")
            ),
            (  # Energy Site Info
                TeslemetryEnergyInfoBinarySensorEntity(energysite, description)
                for energysite in entry.runtime_data.energysites
                for description in ENERGY_INFO_DESCRIPTIONS
                if energysite.info_coordinator.data.get("components_battery")
            ),
        )
    )


class TeslemetryVehicleBinarySensorEntity(TeslemetryVehicleEntity, BinarySensorEntity):
    """Base class for Teslemetry vehicle binary sensors."""

    entity_description: TeslemetryBinarySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""

        if self.coordinator.updated_once:
            if self._value is None:
                self._attr_available = False
                self._attr_is_on = None
            else:
                self._attr_available = True
                self._attr_is_on = self.entity_description.is_on(self._value)
        else:
            self._attr_is_on = None


class TeslemetryEnergyLiveBinarySensorEntity(
    TeslemetryEnergyLiveEntity, BinarySensorEntity
):
    """Base class for Teslemetry energy live binary sensors."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self._value


class TeslemetryEnergyInfoBinarySensorEntity(
    TeslemetryEnergyInfoEntity, BinarySensorEntity
):
    """Base class for Teslemetry energy info binary sensors."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self._value
