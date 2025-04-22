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
        polling_value_fn=lambda x: x == TeslemetryState.ONLINE,
        streaming_listener=lambda x, y: x.listen_State(y),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="cellular",
        streaming_listener=lambda x, y: x.listen_Cellular(y),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="wifi",
        streaming_listener=lambda x, y: x.listen_Wifi(y),
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_battery_heater_on",
        polling=True,
        streaming_listener=lambda x, y: x.listen_BatteryHeaterOn(y),
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_charger_phases",
        polling=True,
        streaming_listener=lambda x, y: x.listen_ChargerPhases(
            lambda z: y(None if z is None else z > 1)
        ),
        polling_value_fn=lambda x: cast(int, x) > 1,
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_state_preconditioning_enabled",
        polling=True,
        streaming_listener=lambda x, y: x.listen_PreconditioningEnabled(y),
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
        streaming_listener=lambda x, y: x.listen_ScheduledChargingPending(y),
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
        streaming_listener=lambda x, y: x.listen_FrontDriverWindow(
            lambda z: y(WINDOW_STATES.get(z))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_fp_window",
        polling=True,
        streaming_listener=lambda x, y: x.listen_FrontPassengerWindow(
            lambda z: y(WINDOW_STATES.get(z))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_rd_window",
        polling=True,
        streaming_listener=lambda x, y: x.listen_RearDriverWindow(
            lambda z: y(WINDOW_STATES.get(z))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_rp_window",
        polling=True,
        streaming_listener=lambda x, y: x.listen_RearPassengerWindow(
            lambda z: y(WINDOW_STATES.get(z))
        ),
        device_class=BinarySensorDeviceClass.WINDOW,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_df",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda x, y: x.listen_FrontDriverDoor(y),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_dr",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda x, y: x.listen_RearDriverDoor(y),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_pf",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda x, y: x.listen_FrontPassengerDoor(y),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="vehicle_state_pr",
        polling=True,
        device_class=BinarySensorDeviceClass.DOOR,
        streaming_listener=lambda x, y: x.listen_RearPassengerDoor(y),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="automatic_blind_spot_camera",
        streaming_listener=lambda x, y: x.listen_AutomaticBlindSpotCamera(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="automatic_emergency_braking_off",
        streaming_listener=lambda x, y: x.listen_AutomaticEmergencyBrakingOff(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="blind_spot_collision_warning_chime",
        streaming_listener=lambda x, y: x.listen_BlindSpotCollisionWarningChime(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="bms_full_charge_complete",
        streaming_listener=lambda x, y: x.listen_BmsFullchargecomplete(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="brake_pedal",
        streaming_listener=lambda x, y: x.listen_BrakePedal(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_port_cold_weather_mode",
        streaming_listener=lambda x, y: x.listen_ChargePortColdWeatherMode(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="service_mode",
        streaming_listener=lambda x, y: x.listen_ServiceMode(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="pin_to_drive_enabled",
        streaming_listener=lambda x, y: x.listen_PinToDriveEnabled(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="drive_rail",
        streaming_listener=lambda x, y: x.listen_DriveRail(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="driver_seat_belt",
        streaming_listener=lambda x, y: x.listen_DriverSeatBelt(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="driver_seat_occupied",
        streaming_listener=lambda x, y: x.listen_DriverSeatOccupied(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="passenger_seat_belt",
        streaming_listener=lambda x, y: x.listen_PassengerSeatBelt(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="fast_charger_present",
        streaming_listener=lambda x, y: x.listen_FastChargerPresent(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="gps_state",
        streaming_listener=lambda x, y: x.listen_GpsState(y),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="guest_mode_enabled",
        streaming_listener=lambda x, y: x.listen_GuestModeEnabled(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="dc_dc_enable",
        streaming_listener=lambda x, y: x.listen_DCDCEnable(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="emergency_lane_departure_avoidance",
        streaming_listener=lambda x, y: x.listen_EmergencyLaneDepartureAvoidance(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="supercharger_session_trip_planner",
        streaming_listener=lambda x, y: x.listen_SuperchargerSessionTripPlanner(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="wiper_heat_enabled",
        streaming_listener=lambda x, y: x.listen_WiperHeatEnabled(y),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="rear_display_hvac_enabled",
        streaming_listener=lambda x, y: x.listen_RearDisplayHvacEnabled(y),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="offroad_lightbar_present",
        streaming_listener=lambda x, y: x.listen_OffroadLightbarPresent(y),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="homelink_nearby",
        streaming_listener=lambda x, y: x.listen_HomelinkNearby(y),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="europe_vehicle",
        streaming_listener=lambda x, y: x.listen_EuropeVehicle(y),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="right_hand_drive",
        streaming_listener=lambda x, y: x.listen_RightHandDrive(y),
        streaming_firmware="2024.44.25",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="located_at_home",
        streaming_listener=lambda x, y: x.listen_LocatedAtHome(y),
        streaming_firmware="2024.44.32",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="located_at_work",
        streaming_listener=lambda x, y: x.listen_LocatedAtWork(y),
        streaming_firmware="2024.44.32",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="located_at_favorite",
        streaming_listener=lambda x, y: x.listen_LocatedAtFavorite(y),
        streaming_firmware="2024.44.32",
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="charge_enable_request",
        streaming_listener=lambda x, y: x.listen_ChargeEnableRequest(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="defrost_for_preconditioning",
        streaming_listener=lambda x, y: x.listen_DefrostForPreconditioning(y),
        entity_registry_enabled_default=False,
        streaming_firmware="2024.44.25",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="lights_high_beams",
        streaming_listener=lambda x, y: x.listen_LightsHighBeams(y),
        entity_registry_enabled_default=False,
        streaming_firmware="2025.2.6",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="seat_vent_enabled",
        streaming_listener=lambda x, y: x.listen_SeatVentEnabled(y),
        entity_registry_enabled_default=False,
        streaming_firmware="2025.2.6",
    ),
    TeslemetryBinarySensorEntityDescription(
        key="speed_limit_mode",
        streaming_listener=lambda x, y: x.listen_SpeedLimitMode(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="remote_start_enabled",
        streaming_listener=lambda x, y: x.listen_RemoteStartEnabled(y),
        entity_registry_enabled_default=False,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="hvil",
        streaming_listener=lambda x, y: x.listen_Hvil(lambda z: y(z == "Fault")),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TeslemetryBinarySensorEntityDescription(
        key="hvac_auto_mode",
        streaming_listener=lambda x, y: x.listen_HvacAutoMode(lambda z: y(z == "On")),
        entity_registry_enabled_default=False,
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
