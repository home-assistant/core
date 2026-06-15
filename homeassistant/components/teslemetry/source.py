"""Command source facades for Teslemetry.

A "source" wraps the cloud API client for a single device and presents the
command methods that the entities and services invoke. Wrapping the client
behind a facade gives the integration one place to add local transports
(BLE for vehicles, a local gateway for Powerwalls) that are read and commanded
local-first with cloud fallback.

In its current form a source forwards every command to the cloud client
unchanged, so behaviour is identical to calling the cloud API directly. Local
transports and the local-first dispatch logic are added in later iterations.
"""

from typing import Any

from tesla_fleet_api.const import (
    CabinOverheatProtectionTemp,
    ClimateKeeperMode,
    EnergyExportMode,
    EnergyOperationMode,
    Level,
    Seat,
    SunRoofCommand,
    Trunk,
    WindowCommand,
)
from tesla_fleet_api.teslemetry import EnergySite, Vehicle


class VehicleSource:
    """Command facade for a Tesla vehicle."""

    def __init__(self, cloud: Vehicle) -> None:
        """Initialize the vehicle source with its cloud client."""
        self.cloud = cloud

    async def wake_up(self) -> dict[str, Any]:
        """Wake up the vehicle."""
        return await self.cloud.wake_up()

    async def flash_lights(self) -> dict[str, Any]:
        """Flash the vehicle's lights."""
        return await self.cloud.flash_lights()

    async def honk_horn(self) -> dict[str, Any]:
        """Honk the vehicle's horn."""
        return await self.cloud.honk_horn()

    async def remote_start_drive(self) -> dict[str, Any]:
        """Enable keyless driving."""
        return await self.cloud.remote_start_drive()

    async def remote_boombox(self, sound: int) -> dict[str, Any]:
        """Play a sound through the vehicle's external speaker."""
        return await self.cloud.remote_boombox(sound=sound)

    async def trigger_homelink(
        self,
        token: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict[str, Any]:
        """Trigger the nearest HomeLink device."""
        return await self.cloud.trigger_homelink(token=token, lat=lat, lon=lon)

    async def auto_conditioning_start(self) -> dict[str, Any]:
        """Start climate control."""
        return await self.cloud.auto_conditioning_start()

    async def auto_conditioning_stop(self) -> dict[str, Any]:
        """Stop climate control."""
        return await self.cloud.auto_conditioning_stop()

    async def set_temps(
        self, driver_temp: float, passenger_temp: float
    ) -> dict[str, Any]:
        """Set the driver and passenger temperatures."""
        return await self.cloud.set_temps(
            driver_temp=driver_temp, passenger_temp=passenger_temp
        )

    async def set_climate_keeper_mode(
        self, climate_keeper_mode: ClimateKeeperMode | int
    ) -> dict[str, Any]:
        """Set the climate keeper mode."""
        return await self.cloud.set_climate_keeper_mode(
            climate_keeper_mode=climate_keeper_mode
        )

    async def set_bioweapon_mode(
        self, on: bool, manual_override: bool
    ) -> dict[str, Any]:
        """Set bioweapon defense mode."""
        return await self.cloud.set_bioweapon_mode(
            on=on, manual_override=manual_override
        )

    async def set_cop_temp(
        self, cop_temp: CabinOverheatProtectionTemp | int
    ) -> dict[str, Any]:
        """Set the cabin overheat protection temperature."""
        return await self.cloud.set_cop_temp(cop_temp=cop_temp)

    async def set_cabin_overheat_protection(
        self, on: bool, fan_only: bool
    ) -> dict[str, Any]:
        """Set cabin overheat protection."""
        return await self.cloud.set_cabin_overheat_protection(on=on, fan_only=fan_only)

    async def window_control(
        self,
        command: str | WindowCommand,
        lat: float | None = None,
        lon: float | None = None,
    ) -> dict[str, Any]:
        """Control the vehicle's windows."""
        return await self.cloud.window_control(command=command, lat=lat, lon=lon)

    async def charge_port_door_open(self) -> dict[str, Any]:
        """Open the charge port door."""
        return await self.cloud.charge_port_door_open()

    async def charge_port_door_close(self) -> dict[str, Any]:
        """Close the charge port door."""
        return await self.cloud.charge_port_door_close()

    async def actuate_trunk(self, which_trunk: Trunk | str) -> dict[str, Any]:
        """Actuate the front or rear trunk."""
        return await self.cloud.actuate_trunk(which_trunk=which_trunk)

    async def sun_roof_control(self, state: str | SunRoofCommand) -> dict[str, Any]:
        """Control the sunroof."""
        return await self.cloud.sun_roof_control(state=state)

    async def door_lock(self) -> dict[str, Any]:
        """Lock the vehicle."""
        return await self.cloud.door_lock()

    async def door_unlock(self) -> dict[str, Any]:
        """Unlock the vehicle."""
        return await self.cloud.door_unlock()

    async def adjust_volume(self, volume: float) -> dict[str, Any]:
        """Adjust the media volume."""
        return await self.cloud.adjust_volume(volume=volume)

    async def media_toggle_playback(self) -> dict[str, Any]:
        """Toggle media playback."""
        return await self.cloud.media_toggle_playback()

    async def media_next_track(self) -> dict[str, Any]:
        """Skip to the next track."""
        return await self.cloud.media_next_track()

    async def media_prev_track(self) -> dict[str, Any]:
        """Skip to the previous track."""
        return await self.cloud.media_prev_track()

    async def set_charging_amps(self, charging_amps: int) -> dict[str, Any]:
        """Set the charging amps."""
        return await self.cloud.set_charging_amps(charging_amps=charging_amps)

    async def set_charge_limit(self, percent: int) -> dict[str, Any]:
        """Set the charge limit."""
        return await self.cloud.set_charge_limit(percent=percent)

    async def remote_seat_heater_request(
        self, seat_position: Seat | int, seat_heater_level: Level | int
    ) -> dict[str, Any]:
        """Set a seat heater level."""
        return await self.cloud.remote_seat_heater_request(
            seat_position=seat_position, seat_heater_level=seat_heater_level
        )

    async def remote_steering_wheel_heat_level_request(
        self, level: Level | int
    ) -> dict[str, Any]:
        """Set the steering wheel heater level."""
        return await self.cloud.remote_steering_wheel_heat_level_request(level=level)

    async def navigation_gps_request(
        self, lat: float, lon: float, order: int | None = None
    ) -> dict[str, Any]:
        """Send a GPS navigation request."""
        return await self.cloud.navigation_gps_request(lat=lat, lon=lon, order=order)

    async def set_scheduled_charging(self, enable: bool, time: int) -> dict[str, Any]:
        """Set scheduled charging."""
        return await self.cloud.set_scheduled_charging(enable=enable, time=time)

    async def set_scheduled_departure(
        self,
        enable: bool = True,
        preconditioning_enabled: bool = False,
        preconditioning_weekdays_only: bool = False,
        departure_time: int = 0,
        off_peak_charging_enabled: bool = False,
        off_peak_charging_weekdays_only: bool = False,
        end_off_peak_time: int = 0,
    ) -> dict[str, Any]:
        """Set a scheduled departure."""
        return await self.cloud.set_scheduled_departure(
            enable=enable,
            preconditioning_enabled=preconditioning_enabled,
            preconditioning_weekdays_only=preconditioning_weekdays_only,
            departure_time=departure_time,
            off_peak_charging_enabled=off_peak_charging_enabled,
            off_peak_charging_weekdays_only=off_peak_charging_weekdays_only,
            end_off_peak_time=end_off_peak_time,
        )

    async def set_valet_mode(
        self, on: bool, password: str | int | None = None
    ) -> dict[str, Any]:
        """Set valet mode."""
        return await self.cloud.set_valet_mode(on=on, password=password)

    async def speed_limit_activate(self, pin: str | int) -> dict[str, Any]:
        """Activate the speed limit."""
        return await self.cloud.speed_limit_activate(pin=pin)

    async def speed_limit_deactivate(self, pin: str | int) -> dict[str, Any]:
        """Deactivate the speed limit."""
        return await self.cloud.speed_limit_deactivate(pin=pin)

    async def add_charge_schedule(
        self,
        days_of_week: str | int,
        enabled: bool,
        lat: float,
        lon: float,
        start_time: int | None = None,
        end_time: int | None = None,
        one_time: bool | None = None,
        id: int | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Add or modify a charge schedule."""
        return await self.cloud.add_charge_schedule(
            days_of_week=days_of_week,
            enabled=enabled,
            lat=lat,
            lon=lon,
            start_time=start_time,
            end_time=end_time,
            one_time=one_time,
            id=id,
            name=name,
        )

    async def remove_charge_schedule(self, id: int) -> dict[str, Any]:
        """Remove a charge schedule."""
        return await self.cloud.remove_charge_schedule(id=id)

    async def add_precondition_schedule(
        self,
        days_of_week: str | int,
        enabled: bool,
        lat: float,
        lon: float,
        precondition_time: int,
        id: int | None = None,
        one_time: bool | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Add or modify a precondition schedule."""
        return await self.cloud.add_precondition_schedule(
            days_of_week=days_of_week,
            enabled=enabled,
            lat=lat,
            lon=lon,
            precondition_time=precondition_time,
            id=id,
            one_time=one_time,
            name=name,
        )

    async def remove_precondition_schedule(self, id: int) -> dict[str, Any]:
        """Remove a precondition schedule."""
        return await self.cloud.remove_precondition_schedule(id=id)

    async def set_sentry_mode(self, on: bool) -> dict[str, Any]:
        """Set sentry mode."""
        return await self.cloud.set_sentry_mode(on=on)

    async def remote_auto_seat_climate_request(
        self, auto_seat_position: int | Seat, auto_climate_on: bool
    ) -> dict[str, Any]:
        """Set automatic seat climate."""
        return await self.cloud.remote_auto_seat_climate_request(
            auto_seat_position=auto_seat_position, auto_climate_on=auto_climate_on
        )

    async def remote_auto_steering_wheel_heat_climate_request(
        self, on: bool
    ) -> dict[str, Any]:
        """Set automatic steering wheel heating."""
        return await self.cloud.remote_auto_steering_wheel_heat_climate_request(on=on)

    async def set_preconditioning_max(
        self, on: bool, manual_override: bool
    ) -> dict[str, Any]:
        """Set max defrost preconditioning."""
        return await self.cloud.set_preconditioning_max(
            on=on, manual_override=manual_override
        )

    async def charge_start(self) -> dict[str, Any]:
        """Start charging."""
        return await self.cloud.charge_start()

    async def charge_stop(self) -> dict[str, Any]:
        """Stop charging."""
        return await self.cloud.charge_stop()

    async def guest_mode(self, enable: bool) -> dict[str, Any]:
        """Set guest mode."""
        return await self.cloud.guest_mode(enable=enable)

    async def schedule_software_update(self, offset_sec: int) -> dict[str, Any]:
        """Schedule a software update."""
        return await self.cloud.schedule_software_update(offset_sec=offset_sec)


class EnergySource:
    """Command facade for a Tesla energy site."""

    def __init__(self, cloud: EnergySite) -> None:
        """Initialize the energy source with its cloud client."""
        self.cloud = cloud

    async def backup(self, backup_reserve_percent: int) -> dict[str, Any]:
        """Set the backup reserve percentage."""
        return await self.cloud.backup(backup_reserve_percent=backup_reserve_percent)

    async def off_grid_vehicle_charging_reserve(
        self, off_grid_vehicle_charging_reserve_percent: int
    ) -> dict[str, Any]:
        """Set the off-grid vehicle charging reserve percentage."""
        return await self.cloud.off_grid_vehicle_charging_reserve(
            off_grid_vehicle_charging_reserve_percent=off_grid_vehicle_charging_reserve_percent
        )

    async def operation(
        self, default_real_mode: EnergyOperationMode | str
    ) -> dict[str, Any]:
        """Set the operation mode."""
        return await self.cloud.operation(default_real_mode=default_real_mode)

    async def grid_import_export(
        self,
        disallow_charge_from_grid_with_solar_installed: bool | None = None,
        customer_preferred_export_rule: EnergyExportMode | str | None = None,
    ) -> dict[str, Any]:
        """Set the grid import/export rules."""
        return await self.cloud.grid_import_export(
            disallow_charge_from_grid_with_solar_installed=disallow_charge_from_grid_with_solar_installed,
            customer_preferred_export_rule=customer_preferred_export_rule,
        )

    async def storm_mode(self, enabled: bool) -> dict[str, Any]:
        """Set storm watch mode."""
        return await self.cloud.storm_mode(enabled=enabled)

    async def time_of_use_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Set the time of use settings."""
        return await self.cloud.time_of_use_settings(settings=settings)
