"""DataUpdateCoordinator for the Hydrawise integration."""

from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import override

from pydrawise import APIError, HydrawiseBase, NotAuthorizedError
from pydrawise.schema import Controller, ControllerWaterUseSummary, Sensor, User, Zone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now, utcnow

from .const import (
    COMMAND_REFRESH_INTERVAL,
    COMMAND_REFRESH_TIMEOUT,
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
    _command_refresh_unsub: CALLBACK_TYPE | None = None
    # When the last command was sent to each controller that hasn't picked it
    # up yet, keyed by controller ID.
    _pending_commands: dict[int, datetime]

    @callback
    def async_refresh_after_command(self, controller: Controller) -> None:
        """Refresh until the controller has picked up a command."""
        self._pending_commands[controller.id] = utcnow()
        self._schedule_command_refresh()

    @callback
    def command_pending(self, controller: Controller) -> bool:
        """Return if the controller has yet to pick up a command."""
        return controller.id in self._pending_commands

    @callback
    def _schedule_command_refresh(self) -> None:
        """Schedule the next refresh while a command is pending."""
        # Keep a refresh that is already scheduled: a burst of commands can't
        # keep pushing it back, and a command sent while a refresh is running
        # doesn't start a second chain of refreshes.
        if self._command_refresh_unsub is not None:
            return
        self._command_refresh_unsub = async_call_later(
            self.hass, COMMAND_REFRESH_INTERVAL, self._async_refresh_after_command
        )

    @callback
    def _async_drop_handled_commands(self, data: HydrawiseData) -> None:
        """Drop the commands the controllers picked up, or that timed out."""
        for controller_id, sent_at in list(self._pending_commands.items()):
            controller = data.controllers.get(controller_id)
            if (
                controller is None
                # pydrawise reports a naive local time, timestamp() makes it
                # comparable.
                or controller.last_contact_time.timestamp() > sent_at.timestamp()
                or utcnow() - sent_at > COMMAND_REFRESH_TIMEOUT
            ):
                del self._pending_commands[controller_id]

    async def _async_refresh_after_command(self, _now: datetime) -> None:
        """Refresh, and keep refreshing until every pending command is handled."""
        self._command_refresh_unsub = None
        await self.async_request_refresh()

        if isinstance(self.last_exception, ConfigEntryAuthFailed):
            # Polling stopped for reauthentication, so stop here too.
            self._pending_commands.clear()
        else:
            # A failed refresh doesn't get to drop timed out commands.
            self._async_drop_handled_commands(self.data)

        if self._pending_commands:
            self._schedule_command_refresh()

    @override
    async def async_shutdown(self) -> None:
        """Stop refreshing after commands, then shut down."""
        if self._command_refresh_unsub is not None:
            self._command_refresh_unsub()
            self._command_refresh_unsub = None
        self._pending_commands.clear()
        await super().async_shutdown()

    @asynccontextmanager
    async def _handle_api_errors(self) -> AsyncIterator[None]:
        """Translate pydrawise errors into coordinator errors."""
        try:
            yield
        except NotAuthorizedError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except APIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
            ) from err


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
        self._pending_commands = {}
        self.new_controllers_callbacks: list[
            Callable[[Iterable[Controller]], None]
        ] = []
        self.new_zones_callbacks: list[
            Callable[[Iterable[tuple[Zone, Controller]]], None]
        ] = []

    @callback
    def async_track_zones(self) -> None:
        """Begin tracking zone and controller add/remove on updates."""
        self.async_add_listener(self._add_remove_zones)

    @override
    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        # Don't fetch zones. We'll fetch them for each controller later.
        # This is to prevent 502 errors in some cases.
        # See: https://github.com/home-assistant/core/issues/120128
        async with self._handle_api_errors():
            data = HydrawiseData(user=await self.api.get_user(fetch_zones=False))
            for controller in data.user.controllers:
                data.controllers[controller.id] = controller
                controller.zones = await self.api.get_zones(controller)
                for zone in controller.zones:
                    data.zones[zone.id] = zone
                    data.zone_id_to_controller[zone.id] = controller
                for sensor in controller.sensors:
                    data.sensors[sensor.id] = sensor
        # Before the entities see the new data, so the ones holding the state
        # of a command they sent know if the controller has picked it up.
        self._async_drop_handled_commands(data)
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
                device_registry.async_remove_device(previous_zones_by_id[zone_id].id)

        if removed_controllers := previous_controllers - current_controllers:
            LOGGER.debug("Removed controllers: %s", ", ".join(removed_controllers))
            for controller_id in removed_controllers:
                device_registry.async_remove_device(
                    previous_controllers_by_id[controller_id].id
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
        self._pending_commands = {}
        self._main_coordinator = main_coordinator

    @callback
    def async_track_zones(self) -> None:
        """Begin tracking zone and controller add/remove on updates."""
        self._main_coordinator.async_add_listener(self._sync_data_from_main)

    @callback
    def _sync_data_from_main(self) -> None:
        """Sync data references from the main coordinator after it updates."""
        if self.data is None or self._main_coordinator.data is None:
            return  # type: ignore[unreachable]
        main_data = self._main_coordinator.data
        self.data.user = main_data.user
        self.data.controllers = main_data.controllers
        self.data.zones = main_data.zones
        self.data.zone_id_to_controller = main_data.zone_id_to_controller
        self.data.sensors = main_data.sensors

    @override
    async def _async_update_data(self) -> HydrawiseData:
        """Fetch the latest data from Hydrawise."""
        daily_water_summary: dict[int, ControllerWaterUseSummary] = {}
        async with self._handle_api_errors():
            for controller in self._main_coordinator.data.controllers.values():
                daily_water_summary[
                    controller.id
                ] = await self.api.get_water_use_summary(
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
