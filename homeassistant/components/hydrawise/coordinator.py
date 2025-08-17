"""DataUpdateCoordinator for the Hydrawise integration."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from pydrawise import HydrawiseBase
from pydrawise.schema import Controller, ControllerWaterUseSummary, Sensor, User, Zone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import now

from .const import (
    DOMAIN,
    LOGGER,
    MAIN_SCAN_INTERVAL,
    MODEL_ZONE,
    WATER_USE_SCAN_INTERVAL,
)

type HydrawiseConfigEntry = ConfigEntry[HydrawiseUpdateCoordinators]


@dataclass
class HydrawiseData:
    """Container for data fetched from the Hydrawise API."""

    user: User
    controllers: dict[int, Controller] = field(default_factory=dict)
    zones: dict[int, Zone] = field(default_factory=dict)
    zone_id_to_controller: dict[int, Controller] = field(default_factory=dict)
    sensors: dict[int, Sensor] = field(default_factory=dict)
    daily_water_summary: dict[int, ControllerWaterUseSummary] = field(
        default_factory=dict
    )


@dataclass
class HydrawiseUpdateCoordinators:
    """Container for all Hydrawise DataUpdateCoordinator instances."""

    main: HydrawiseMainDataUpdateCoordinator
    water_use: HydrawiseWaterUseDataUpdateCoordinator


class HydrawiseDataUpdateCoordinator(DataUpdateCoordinator[HydrawiseData]):
    """Base class for Hydrawise Data Update Coordinators."""

    api: HydrawiseBase
    config_entry: HydrawiseConfigEntry


class HydrawiseMainDataUpdateCoordinator(HydrawiseDataUpdateCoordinator):
    """The main Hydrawise Data Update Coordinator.

    This fetches the primary state data for Hydrawise controllers and zones
    at a relatively frequent interval so that the primary functions of the
    integration are updated in a timely manner.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HydrawiseConfigEntry,
        api: HydrawiseBase,
    ) -> None:
        """Initialize HydrawiseDataUpdateCoordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=MAIN_SCAN_INTERVAL,
        )
        self.api = api
        self.new_controllers_callbacks: list[
            Callable[[Iterable[Controller]], None]
        ] = []
        self.new_zones_callbacks: list[
            Callable[[Iterable[tuple[Zone, Controller]]], None]
        ] = []
        self.async_add_listener(self._add_remove_zones)

    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        # Don't fetch zones. We'll fetch them for each controller later.
        # This is to prevent 502 errors in some cases.
        # See: https://github.com/home-assistant/core/issues/120128
        data = HydrawiseData(user=await self.api.get_user(fetch_zones=False))
        for controller in data.user.controllers:
            data.controllers[controller.id] = controller
            controller.zones = await self.api.get_zones(controller)
            for zone in controller.zones:
                data.zones[zone.id] = zone
                data.zone_id_to_controller[zone.id] = controller
            for sensor in controller.sensors:
                data.sensors[sensor.id] = sensor
        return data

    @callback
    def _add_remove_zones(self) -> None:
        """Add newly discovered zones and remove nonexistent ones."""
        if self.data is None:
            # Likely a setup error; ignore.
            # Despite what mypy thinks, this is still reachable. Without this check,
            # the test_connect_retry test in test_init.py fails.
            return  # type: ignore[unreachable]

        device_registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )
        previous_zones: set[str] = set()
        previous_zones_by_id: dict[str, DeviceEntry] = {}
        previous_controllers: set[str] = set()
        previous_controllers_by_id: dict[str, DeviceEntry] = {}
        for device in devices:
            for domain, identifier in device.identifiers:
                if domain == DOMAIN:
                    if device.model == MODEL_ZONE:
                        previous_zones.add(identifier)
                        previous_zones_by_id[identifier] = device
                    else:
                        previous_controllers.add(identifier)
                        previous_controllers_by_id[identifier] = device
                    continue

        current_zones = {str(zone_id) for zone_id in self.data.zones}
        current_controllers = {
            str(controller_id) for controller_id in self.data.controllers
        }

        if removed_zones := previous_zones - current_zones:
            LOGGER.debug("Removed zones: %s", ", ".join(removed_zones))
            for zone_id in removed_zones:
                device_registry.async_update_device(
                    device_id=previous_zones_by_id[zone_id].id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

        if removed_controllers := previous_controllers - current_controllers:
            LOGGER.debug("Removed controllers: %s", ", ".join(removed_controllers))
            for controller_id in removed_controllers:
                device_registry.async_update_device(
                    device_id=previous_controllers_by_id[controller_id].id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

        if new_controller_ids := current_controllers - previous_controllers:
            LOGGER.debug("New controllers found: %s", ", ".join(new_controller_ids))
            new_controllers = [
                self.data.controllers[controller_id]
                for controller_id in map(int, new_controller_ids)
            ]
            for new_controller_callback in self.new_controllers_callbacks:
                new_controller_callback(new_controllers)

        if new_zone_ids := current_zones - previous_zones:
            LOGGER.debug("New zones found: %s", ", ".join(new_zone_ids))
            new_zones = [
                (
                    self.data.zones[zone_id],
                    self.data.zone_id_to_controller[zone_id],
                )
                for zone_id in map(int, new_zone_ids)
            ]
            for new_zone_callback in self.new_zones_callbacks:
                new_zone_callback(new_zones)


class HydrawiseWaterUseDataUpdateCoordinator(HydrawiseDataUpdateCoordinator):
    """Data Update Coordinator for Hydrawise Water Use.

    This fetches data that is more expensive for the Hydrawise API to compute
    at a less frequent interval as to not overload the Hydrawise servers.
    """

    _main_coordinator: HydrawiseMainDataUpdateCoordinator

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HydrawiseConfigEntry,
        api: HydrawiseBase,
        main_coordinator: HydrawiseMainDataUpdateCoordinator,
    ) -> None:
        """Initialize HydrawiseWaterUseDataUpdateCoordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} water use",
            update_interval=WATER_USE_SCAN_INTERVAL,
        )
        self.api = api
        self._main_coordinator = main_coordinator

    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        daily_water_summary: dict[int, ControllerWaterUseSummary] = {}
        for controller in self._main_coordinator.data.controllers.values():
            daily_water_summary[controller.id] = await self.api.get_water_use_summary(
                controller,
                now().replace(hour=0, minute=0, second=0, microsecond=0),
                now(),
            )
        main_data = self._main_coordinator.data
        return HydrawiseData(
            user=main_data.user,
            controllers=main_data.controllers,
            zones=main_data.zones,
            sensors=main_data.sensors,
            daily_water_summary=daily_water_summary,
        )
