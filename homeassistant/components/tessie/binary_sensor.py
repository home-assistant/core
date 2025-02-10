"""Binary Sensor platform for Tessie integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TessieConfigEntry
from .const import TessieState
from .entity import TessieEnergyEntity, TessieEntity
from .models import TessieEnergyData, TessieVehicleData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TessieBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Tessie binary sensor entity."""

    is_on: Callable[..., bool] = lambda x: x


VEHICLE_DESCRIPTIONS: tuple[TessieBinarySensorEntityDescription, ...] = (
    TessieBinarySensorEntityDescription(
        key="state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on=lambda x: x == TessieState.ONLINE,
    ),
    TessieBinarySensorEntityDescription(
        key="climate_state_battery_heater",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="charge_state_charging_state",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on=lambda x: x == "Charging",
        entity_registry_enabled_default=False,
    ),
    TessieBinarySensorEntityDescription(
        key="charge_state_preconditioning_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="charge_state_scheduled_charging_pending",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="charge_state_trip_charging",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="charge_state_conn_charge_cable",
        is_on=lambda x: x != "<invalid>",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TessieBinarySensorEntityDescription(
        key="climate_state_auto_seat_climate_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="climate_state_auto_seat_climate_right",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="climate_state_auto_steering_wheel_heat",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="climate_state_cabin_overheat_protection",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on=lambda x: x == "On",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="climate_state_cabin_overheat_protection_actively_cooling",
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_dashcam_state",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on=lambda x: x == "Recording",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_is_user_present",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_fl",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_fr",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_rl",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_rr",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_fd_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_fp_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_rd_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_rp_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_df",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_dr",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_pf",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TessieBinarySensorEntityDescription(
        key="vehicle_state_pr",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENERGY_LIVE_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(key="backup_capable"),
    BinarySensorEntityDescription(key="grid_services_active"),
    BinarySensorEntityDescription(key="storm_mode_active"),
)


ENERGY_INFO_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="components_grid_services_enabled",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie binary sensor platform from a config entry."""
    async_add_entities(
        chain(
            (
                TessieBinarySensorEntity(vehicle, description)
                for vehicle in entry.runtime_data.vehicles
                for description in VEHICLE_DESCRIPTIONS
            ),
            (
                TessieEnergyLiveBinarySensorEntity(energy, description)
                for energy in entry.runtime_data.energysites
                for description in ENERGY_LIVE_DESCRIPTIONS
            ),
            (
                TessieEnergyInfoBinarySensorEntity(vehicle, description)
                for vehicle in entry.runtime_data.energysites
                for description in ENERGY_INFO_DESCRIPTIONS
            ),
        )
    )


class TessieBinarySensorEntity(TessieEntity, BinarySensorEntity):
    """Base class for Tessie binary sensors."""

    entity_description: TessieBinarySensorEntityDescription

    def __init__(
        self,
        vehicle: TessieVehicleData,
        description: TessieBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on(self._value)


class TessieEnergyLiveBinarySensorEntity(TessieEnergyEntity, BinarySensorEntity):
    """Base class for Tessie energy live binary sensors."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        data: TessieEnergyData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, data.live_coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self._value


class TessieEnergyInfoBinarySensorEntity(TessieEnergyEntity, BinarySensorEntity):
    """Base class for Tessie energy info binary sensors."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        data: TessieEnergyData,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, data.info_coordinator, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self._value
