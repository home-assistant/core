"""Representation of a deCONZ gateway."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from pydeconz import DeconzSession
from pydeconz.interfaces import sensors
from pydeconz.interfaces.api_handlers import APIHandler, GroupedAPIHandler
from pydeconz.interfaces.groups import GroupHandler
from pydeconz.models.event import EventType

from homeassistant.config_entries import SOURCE_HASSIO
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from ..const import CONF_MASTER_GATEWAY, DOMAIN, HASSIO_CONFIGURATION_URL, PLATFORMS
from .config import DeconzConfig

if TYPE_CHECKING:
    from .. import DeconzConfigEntry
    from ..deconz_event import (
        DeconzAlarmEvent,
        DeconzEvent,
        DeconzPresenceEvent,
        DeconzRelativeRotaryEvent,
    )

SENSORS = (
    sensors.SensorResourceManager,
    sensors.AirPurifierHandler,
    sensors.AirQualityHandler,
    sensors.AlarmHandler,
    sensors.AncillaryControlHandler,
    sensors.BatteryHandler,
    sensors.CarbonMonoxideHandler,
    sensors.ConsumptionHandler,
    sensors.DaylightHandler,
    sensors.DoorLockHandler,
    sensors.FireHandler,
    sensors.GenericFlagHandler,
    sensors.GenericStatusHandler,
    sensors.HumidityHandler,
    sensors.LightLevelHandler,
    sensors.OpenCloseHandler,
    sensors.PowerHandler,
    sensors.PresenceHandler,
    sensors.PressureHandler,
    sensors.RelativeRotaryHandler,
    sensors.SwitchHandler,
    sensors.TemperatureHandler,
    sensors.ThermostatHandler,
    sensors.TimeHandler,
    sensors.VibrationHandler,
    sensors.WaterHandler,
)


class DeconzHub:
    """Manages a single deCONZ gateway."""

    def __init__(
        self, hass: HomeAssistant, config_entry: DeconzConfigEntry, api: DeconzSession
    ) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config = DeconzConfig.from_config_entry(config_entry)
        self.config_entry = config_entry
        self.api = api

        api.connection_status_callback = self.async_connection_status_callback

        self.available = True
        self.ignore_state_updates = False

        self.signal_reachable = f"deconz-reachable-{config_entry.entry_id}"

        self.deconz_ids: dict[str, str] = {}
        self.entities: dict[str, set[str]] = {}
        self.events: list[
            DeconzAlarmEvent
            | DeconzEvent
            | DeconzPresenceEvent
            | DeconzRelativeRotaryEvent
        ] = []
        self.clip_sensors: set[tuple[Callable[[EventType, str], None], str]] = set()
        self.deconz_groups: set[tuple[Callable[[EventType, str], None], str]] = set()
        self.ignored_devices: set[tuple[Callable[[EventType, str], None], str]] = set()

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return cast(str, self.config_entry.unique_id)

    @property
    def master(self) -> bool:
        """Gateway which is used with deCONZ services without defining id."""
        return cast(bool, self.config_entry.options[CONF_MASTER_GATEWAY])

    @callback
    def register_platform_add_device_callback(
        self,
        add_device_callback: Callable[[EventType, str], None],
        deconz_device_interface: APIHandler | GroupedAPIHandler,
        always_ignore_clip_sensors: bool = False,
    ) -> None:
        """Wrap add_device_callback to check allow_new_devices option."""

        initializing = True

        def async_add_device(_: EventType, device_id: str) -> None:
            """Add device or add it to ignored_devices set.

            If ignore_state_updates is True means device_refresh service is used.
            Device_refresh is expected to load new devices.
            """
            if (
                not initializing
                and not self.config.allow_new_devices
                and not self.ignore_state_updates
            ):
                self.ignored_devices.add((async_add_device, device_id))
                return

            if isinstance(deconz_device_interface, GroupHandler):
                self.deconz_groups.add((async_add_device, device_id))
                if not self.config.allow_deconz_groups:
                    return

            if isinstance(deconz_device_interface, SENSORS):
                device = deconz_device_interface[device_id]
                if device.type.startswith("CLIP") and not always_ignore_clip_sensors:
                    self.clip_sensors.add((async_add_device, device_id))
                    if not self.config.allow_clip_sensor:
                        return

            add_device_callback(EventType.ADDED, device_id)

        self.config_entry.async_on_unload(
            deconz_device_interface.subscribe(
                async_add_device,
                EventType.ADDED,
            )
        )

        for device_id in sorted(deconz_device_interface, key=int):
            async_add_device(EventType.ADDED, device_id)

        initializing = False

    @callback
    def load_ignored_devices(self) -> None:
        """Load previously ignored devices."""
        for add_entities, device_id in self.ignored_devices:
            add_entities(EventType.ADDED, device_id)
        self.ignored_devices.clear()

    # Callbacks

    @callback
    def async_connection_status_callback(self, available: bool) -> None:
        """Handle signals of gateway connection status."""
        self.available = available
        self.ignore_state_updates = False
        async_dispatcher_send(self.hass, self.signal_reachable)

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        if self.api.config.mac is None:
            return

        device_registry = dr.async_get(self.hass)

        # Host device
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.api.config.mac)},
        )

        # Gateway service
        configuration_url = f"http://{self.config.host}:{self.config.port}"
        if self.config_entry.source == SOURCE_HASSIO:
            configuration_url = HASSIO_CONFIGURATION_URL
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            configuration_url=configuration_url,
            entry_type=dr.DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self.api.config.bridge_id)},
            manufacturer="Dresden Elektronik",
            model=self.api.config.model_id,
            name=self.api.config.name,
            sw_version=self.api.config.software_version,
            via_device=(CONNECTION_NETWORK_MAC, self.api.config.mac),
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, config_entry: DeconzConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        This is a static method because a class method (bound method),
        cannot be used with weak references.
        Causes for this is either discovery updating host address or
        config entry options changing.
        """
        hub = config_entry.runtime_data
        previous_config = hub.config
        hub.config = DeconzConfig.from_config_entry(config_entry)
        if previous_config.host != hub.config.host:
            hub.api.close()
            hub.api.host = hub.config.host
            hub.api.start()
            return

        await hub.options_updated(previous_config)

    async def options_updated(self, previous_config: DeconzConfig) -> None:
        """Manage entities affected by config entry options."""
        deconz_ids = []

        # Allow CLIP sensors

        if self.config.allow_clip_sensor != previous_config.allow_clip_sensor:
            if self.config.allow_clip_sensor:
                for add_device, device_id in self.clip_sensors:
                    add_device(EventType.ADDED, device_id)
            else:
                deconz_ids += [
                    sensor.deconz_id
                    for sensor in self.api.sensors.values()
                    if sensor.type.startswith("CLIP")
                ]

        # Allow Groups

        if self.config.allow_deconz_groups != previous_config.allow_deconz_groups:
            if self.config.allow_deconz_groups:
                for add_device, device_id in self.deconz_groups:
                    add_device(EventType.ADDED, device_id)
            else:
                deconz_ids += [group.deconz_id for group in self.api.groups.values()]

        # Allow adding new devices

        if self.config.allow_new_devices != previous_config.allow_new_devices:
            if self.config.allow_new_devices:
                self.load_ignored_devices()

        # Remove entities based on above categories

        entity_registry = er.async_get(self.hass)

        # Copy the ids since calling async_remove will modify the dict
        # and will cause a runtime error because the dict size changes
        # during iteration
        for entity_id, deconz_id in self.deconz_ids.copy().items():
            if deconz_id in deconz_ids and entity_registry.async_is_registered(
                entity_id
            ):
                # Removing an entity from the entity registry will also remove them
                # from Home Assistant
                entity_registry.async_remove(entity_id)

    @callback
    def shutdown(self, event: Event) -> None:
        """Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.close()

    async def async_reset(self) -> bool:
        """Reset this gateway to default state."""
        self.api.connection_status_callback = None
        self.api.close()

        await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

        self.deconz_ids = {}
        return True
