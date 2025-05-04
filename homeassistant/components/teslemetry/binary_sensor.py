"""Binary Sensor platform for Teslemetry integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from teslemetry_stream.vehicle import TeslemetryStreamVehicle

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType

from . import TeslemetryConfigEntry
from .const import TeslemetryState
from .entity import (
    TeslemetryEnergyInfoEntity,
    TeslemetryEnergyLiveEntity,
    TeslemetryVehicleEntity,
    TeslemetryVehicleStreamEntity,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData

PARALLEL_UPDATES = 0

WINDOW_STATES = {
    "Opened": True,
    "PartiallyOpen": True,
    "Closed": False,
}


@dataclass(frozen=True, kw_only=True)
class TeslemetryBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Teslemetry binary sensor entity."""

    polling_value_fn: Callable[[StateType], bool | None] = bool
    polling: bool = False
    streaming_listener: (
        Callable[
            [TeslemetryStreamVehicle, Callable[[bool | None], None]],
            Callable[[], None],
        ]
        | None
    ) = None
    streaming_firmware: str = "2024.26"


VEHICLE_DESCRIPTIONS: tuple[TeslemetryBinarySensorEntityDescription, ...] = (
    TeslemetryBinarySensorEntityDescription(
        key="state",
        polling=True,
        polling_value_fn=lambda value: value == TeslemetryState.ONLINE,
        streaming_listener=lambda vehicle, callback: vehicle.listen_State(callback),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="cellular",
        streaming_listener=lambda vehicle, callback: vehicle.listen_Cellular(callback),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="wifi",
        streaming_listener=lambda vehicle, callback: vehicle.listen_Wifi(callback),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_battery_heater_on",
        polling=True,
        streaming_listener=lambda vehicle, callback: vehicle.listen_BatteryHeaterOn(
            callback
        ),
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_charger_phases",
        polling=True,
        streaming_listener=lambda vehicle, callback: vehicle.listen_ChargerPhases(
            lambda value: callback(None if value is None else value > 1)
        ),
        polling_value_fn=lambda x: cast(int, x) > 1,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_preconditioning_enabled",
        polling=True,
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_PreconditioningEnabled(callback),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="climate_state_is_preconditioning",
        polling=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_scheduled_charging_pending",
        polling=True,
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_ScheduledChargingPending(callback),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_trip_charging",
        polling=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_conn_charge_cable",
        polling=True,
        polling_value_fn=lambda x: x != "<invalid>",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="climate_state_cabin_overheat_protection_actively_cooling",
        polling=True,
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_dashcam_state",
        polling=True,
        device_class=BinarySensorDeviceClass.RUNNING,
        polling_value_fn=lambda x: x == "Recording",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_is_user_present",
        polling=True,
        device_class=BinarySensorDeviceClass.PRESENCE,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_fl",
        polling=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_fr",
        polling=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_rl",
        polling=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_tpms_soft_warning_rr",
        polling=True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_fd_window",
        polling=True,
        streaming_listener=lambda vehicle, callback: vehicle.listen_FrontDriverWindow(
            lambda value: callback(None if value is None else WINDOW_STATES.get(value))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_fp_window",
        polling=True,
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_FrontPassengerWindow(
            lambda value: callback(None if value is None else WINDOW_STATES.get(value))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_rd_window",
        polling=True,
        streaming_listener=lambda vehicle, callback: vehicle.listen_RearDriverWindow(
            lambda value: callback(None if value is None else WINDOW_STATES.get(value))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_rp_window",
        polling=True,
        streaming_listener=lambda vehicle, callback: vehicle.listen_RearPassengerWindow(
            lambda value: callback(None if value is None else WINDOW_STATES.get(value))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_df",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda vehicle, callback: vehicle.listen_FrontDriverDoor(
            callback
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_dr",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda vehicle, callback: vehicle.listen_RearDriverDoor(
            callback
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_pf",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda vehicle, callback: vehicle.listen_FrontPassengerDoor(
            callback
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_pr",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda vehicle, callback: vehicle.listen_RearPassengerDoor(
            callback
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="automatic_blind_spot_camera",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_AutomaticBlindSpotCamera(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="automatic_emergency_braking_off",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_AutomaticEmergencyBrakingOff(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="blind_spot_collision_warning_chime",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_BlindSpotCollisionWarningChime(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="bms_full_charge_complete",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_BmsFullchargecomplete(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="brake_pedal",
        streaming_listener=lambda vehicle, callback: vehicle.listen_BrakePedal(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_port_cold_weather_mode",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_ChargePortColdWeatherMode(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="service_mode",
        streaming_listener=lambda vehicle, callback: vehicle.listen_ServiceMode(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="pin_to_drive_enabled",
        streaming_listener=lambda vehicle, callback: vehicle.listen_PinToDriveEnabled(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="drive_rail",
        streaming_listener=lambda vehicle, callback: vehicle.listen_DriveRail(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="driver_seat_belt",
        streaming_listener=lambda vehicle, callback: vehicle.listen_DriverSeatBelt(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="driver_seat_occupied",
        streaming_listener=lambda vehicle, callback: vehicle.listen_DriverSeatOccupied(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="passenger_seat_belt",
        streaming_listener=lambda vehicle, callback: vehicle.listen_PassengerSeatBelt(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="fast_charger_present",
        streaming_listener=lambda vehicle, callback: vehicle.listen_FastChargerPresent(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="gps_state",
        streaming_listener=lambda vehicle, callback: vehicle.listen_GpsState(callback),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="guest_mode_enabled",
        streaming_listener=lambda vehicle, callback: vehicle.listen_GuestModeEnabled(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="dc_dc_enable",
        streaming_listener=lambda vehicle, callback: vehicle.listen_DCDCEnable(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="emergency_lane_departure_avoidance",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_EmergencyLaneDepartureAvoidance(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="supercharger_session_trip_planner",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_SuperchargerSessionTripPlanner(callback),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="wiper_heat_enabled",
        streaming_listener=lambda vehicle, callback: vehicle.listen_WiperHeatEnabled(
            callback
        ),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="rear_display_hvac_enabled",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_RearDisplayHvacEnabled(callback),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="offroad_lightbar_present",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_OffroadLightbarPresent(callback),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="homelink_nearby",
        streaming_listener=lambda vehicle, callback: vehicle.listen_HomelinkNearby(
            callback
        ),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="europe_vehicle",
        streaming_listener=lambda vehicle, callback: vehicle.listen_EuropeVehicle(
            callback
        ),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="right_hand_drive",
        streaming_listener=lambda vehicle, callback: vehicle.listen_RightHandDrive(
            callback
        ),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="located_at_home",
        streaming_listener=lambda vehicle, callback: vehicle.listen_LocatedAtHome(
            callback
        ),
        streaming_firmware="2024.44.32",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="located_at_work",
        streaming_listener=lambda vehicle, callback: vehicle.listen_LocatedAtWork(
            callback
        ),
        streaming_firmware="2024.44.32",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="located_at_favorite",
        streaming_listener=lambda vehicle, callback: vehicle.listen_LocatedAtFavorite(
            callback
        ),
        streaming_firmware="2024.44.32",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_enable_request",
        streaming_listener=lambda vehicle, callback: vehicle.listen_ChargeEnableRequest(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="defrost_for_preconditioning",
        streaming_listener=lambda vehicle,
        callback: vehicle.listen_DefrostForPreconditioning(callback),
        entity_registry_enabled_default=False,
        streaming_firmware="2024.44.25",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="lights_hazards_active",
        streaming_listener=lambda x, y: x.listen_LightsHazardsActive(y),
        entity_registry_enabled_default=False,
        streaming_firmware="2025.2.6",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="lights_high_beams",
        streaming_listener=lambda vehicle, callback: vehicle.listen_LightsHighBeams(
            callback
        ),
        entity_registry_enabled_default=False,
        streaming_firmware="2025.2.6",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="seat_vent_enabled",
        streaming_listener=lambda vehicle, callback: vehicle.listen_SeatVentEnabled(
            callback
        ),
        entity_registry_enabled_default=False,
        streaming_firmware="2025.2.6",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="speed_limit_mode",
        streaming_listener=lambda vehicle, callback: vehicle.listen_SpeedLimitMode(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="remote_start_enabled",
        streaming_listener=lambda vehicle, callback: vehicle.listen_RemoteStartEnabled(
            callback
        ),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="hvil",
        streaming_listener=lambda vehicle, callback: vehicle.listen_Hvil(
            lambda value: callback(None if value is None else value == "Fault")
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="hvac_auto_mode",
        streaming_listener=lambda vehicle, callback: vehicle.listen_HvacAutoMode(
            lambda value: callback(None if value is None else value == "On")
        ),
        entity_registry_enabled_default=False,
    ),
)


ENERGY_LIVE_DESCRIPTIONS: tuple[TeslemetryBinarySensorEntityDescription, ...] = (
    TeslemetryBinarySensorEntityDescription(
        key="grid_status",
        polling_value_fn=lambda value: value == "Active",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="backup_capable", entity_category=EntityCategory.DIAGNOSTIC
    ),
    TeslemetryBinarySensorEntityDescription(
        key="grid_services_active", entity_category=EntityCategory.DIAGNOSTIC
    ),
    TeslemetryBinarySensorEntityDescription(key="storm_mode_active"),
)


ENERGY_INFO_DESCRIPTIONS: tuple[TeslemetryBinarySensorEntityDescription, ...] = (
    TeslemetryBinarySensorEntityDescription(
        key="components_grid_services_enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry binary sensor platform from a config entry."""

    entities: list[BinarySensorEntity] = []
    for vehicle in entry.runtime_data.vehicles:
        for description in VEHICLE_DESCRIPTIONS:
            if (
                not vehicle.api.pre2021
                and description.streaming_listener
                and vehicle.firmware >= description.streaming_firmware
            ):
                entities.append(
                    TeslemetryVehicleStreamingBinarySensorEntity(vehicle, description)
                )
            elif description.polling:
                entities.append(
                    TeslemetryVehiclePollingBinarySensorEntity(vehicle, description)
                )

    entities.extend(
        TeslemetryEnergyLiveBinarySensorEntity(energysite, description)
        for energysite in entry.runtime_data.energysites
        if energysite.live_coordinator
        for description in ENERGY_LIVE_DESCRIPTIONS
        if description.key in energysite.live_coordinator.data
    )
    entities.extend(
        TeslemetryEnergyInfoBinarySensorEntity(energysite, description)
        for energysite in entry.runtime_data.energysites
        for description in ENERGY_INFO_DESCRIPTIONS
        if description.key in energysite.info_coordinator.data
    )

    async_add_entities(entities)


class TeslemetryVehiclePollingBinarySensorEntity(
    TeslemetryVehicleEntity, BinarySensorEntity
):
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

        self._attr_available = self._value is not None
        if self._attr_available:
            assert self._value is not None
            self._attr_is_on = self.entity_description.polling_value_fn(self._value)


class TeslemetryVehicleStreamingBinarySensorEntity(
    TeslemetryVehicleStreamEntity, BinarySensorEntity, RestoreEntity
):
    """Base class for Teslemetry vehicle streaming sensors."""

    entity_description: TeslemetryBinarySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryVehicleData,
        description: TeslemetryBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_is_on = state.state == STATE_ON

        assert self.entity_description.streaming_listener
        self.async_on_remove(
            self.entity_description.streaming_listener(
                self.vehicle.stream_vehicle, self._async_value_from_stream
            )
        )

    def _async_value_from_stream(self, value: bool | None) -> None:
        """Update the value of the entity."""
        self._attr_available = value is not None
        self._attr_is_on = value
        self.async_write_ha_state()


class TeslemetryEnergyLiveBinarySensorEntity(
    TeslemetryEnergyLiveEntity, BinarySensorEntity
):
    """Base class for Teslemetry energy live binary sensors."""

    entity_description: TeslemetryBinarySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: TeslemetryBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self.entity_description.polling_value_fn(self._value)


class TeslemetryEnergyInfoBinarySensorEntity(
    TeslemetryEnergyInfoEntity, BinarySensorEntity
):
    """Base class for Teslemetry energy info binary sensors."""

    entity_description: TeslemetryBinarySensorEntityDescription

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: TeslemetryBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(data, description.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the binary sensor."""
        self._attr_is_on = self.entity_description.polling_value_fn(self._value)
