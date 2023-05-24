"""Representation of a deCONZ gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

import async_timeout
from pydeconz import DeconzSession, errors
from pydeconz.interfaces import sensors
from pydeconz.interfaces.api_handlers import APIHandler, GroupedAPIHandler
from pydeconz.interfaces.groups import GroupHandler
from pydeconz.models.event import EventType

from homeassistant.config_entries import SOURCE_HASSIO, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_ALLOW_NEW_DEVICES,
    CONF_MASTER_GATEWAY,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DEFAULT_ALLOW_NEW_DEVICES,
    DOMAIN as DECONZ_DOMAIN,
    HASSIO_CONFIGURATION_URL,
    LOGGER,
    PLATFORMS,
)
from .errors import AuthenticationRequired, CannotConnect

if TYPE_CHECKING:
    from .deconz_event import (
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


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: DeconzSession
    ) -> None:
        """Initialize the system."""
        self.hass = hass
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

        self.option_allow_clip_sensor = self.config_entry.options.get(
            CONF_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_CLIP_SENSOR
        )
        self.option_allow_deconz_groups = config_entry.options.get(
            CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS
        )
        self.option_allow_new_devices = config_entry.options.get(
            CONF_ALLOW_NEW_DEVICES, DEFAULT_ALLOW_NEW_DEVICES
        )

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return cast(str, self.config_entry.unique_id)

    @property
    def host(self) -> str:
        """Return the host of the gateway."""
        return cast(str, self.config_entry.data[CONF_HOST])

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
                and not self.option_allow_new_devices
                and not self.ignore_state_updates
            ):
                self.ignored_devices.add((async_add_device, device_id))
                return

            if isinstance(deconz_device_interface, GroupHandler):
                self.deconz_groups.add((async_add_device, device_id))
                if not self.option_allow_deconz_groups:
                    return

            if isinstance(deconz_device_interface, SENSORS):
                device = deconz_device_interface[device_id]
                if device.type.startswith("CLIP") and not always_ignore_clip_sensors:
                    self.clip_sensors.add((async_add_device, device_id))
                    if not self.option_allow_clip_sensor:
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
        configuration_url = f"http://{self.host}:{self.config_entry.data[CONF_PORT]}"
        if self.config_entry.source == SOURCE_HASSIO:
            configuration_url = HASSIO_CONFIGURATION_URL
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            configuration_url=configuration_url,
            entry_type=dr.DeviceEntryType.SERVICE,
            identifiers={(DECONZ_DOMAIN, self.api.config.bridge_id)},
            manufacturer="Dresden Elektronik",
            model=self.api.config.model_id,
            name=self.api.config.name,
            sw_version=self.api.config.software_version,
            via_device=(CONNECTION_NETWORK_MAC, self.api.config.mac),
        )

    @staticmethod
    async def async_config_entry_updated(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle signals of config entry being updated.

        This is a static method because a class method (bound method),
        cannot be used with weak references.
        Causes for this is either discovery updating host address or
        config entry options changing.
        """
        if entry.entry_id not in hass.data[DECONZ_DOMAIN]:
            # A race condition can occur if multiple config entries are
            # unloaded in parallel
            return
        gateway = get_gateway_from_config_entry(hass, entry)

        if gateway.api.host != gateway.host:
            gateway.api.close()
            gateway.api.host = gateway.host
            gateway.api.start()
            return

        await gateway.options_updated()

    async def options_updated(self) -> None:
        """Manage entities affected by config entry options."""
        deconz_ids = []

        # Allow CLIP sensors

        option_allow_clip_sensor = self.config_entry.options.get(
            CONF_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_CLIP_SENSOR
        )
        if option_allow_clip_sensor != self.option_allow_clip_sensor:
            self.option_allow_clip_sensor = option_allow_clip_sensor
            if option_allow_clip_sensor:
                for add_device, device_id in self.clip_sensors:
                    add_device(EventType.ADDED, device_id)
            else:
                deconz_ids += [
                    sensor.deconz_id
                    for sensor in self.api.sensors.values()
                    if sensor.type.startswith("CLIP")
                ]

        # Allow Groups

        option_allow_deconz_groups = self.config_entry.options.get(
            CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS
        )
        if option_allow_deconz_groups != self.option_allow_deconz_groups:
            self.option_allow_deconz_groups = option_allow_deconz_groups
            if option_allow_deconz_groups:
                for add_device, device_id in self.deconz_groups:
                    add_device(EventType.ADDED, device_id)
            else:
                deconz_ids += [group.deconz_id for group in self.api.groups.values()]

        # Allow adding new devices

        option_allow_new_devices = self.config_entry.options.get(
            CONF_ALLOW_NEW_DEVICES, DEFAULT_ALLOW_NEW_DEVICES
        )
        if option_allow_new_devices != self.option_allow_new_devices:
            self.option_allow_new_devices = option_allow_new_devices
            if option_allow_new_devices:
                self.load_ignored_devices()

        # Remove entities based on above categories

        entity_registry = er.async_get(self.hass)

        for entity_id, deconz_id in self.deconz_ids.items():
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


@callback
def get_gateway_from_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> DeconzGateway:
    """Return gateway with a matching config entry ID."""
    return cast(DeconzGateway, hass.data[DECONZ_DOMAIN][config_entry.entry_id])


async def get_deconz_session(
    hass: HomeAssistant,
    config: MappingProxyType[str, Any],
) -> DeconzSession:
    """Create a gateway object and verify configuration."""
    session = aiohttp_client.async_get_clientsession(hass)

    deconz_session = DeconzSession(
        session,
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_API_KEY],
    )
    try:
        async with async_timeout.timeout(10):
            await deconz_session.refresh_state()
        return deconz_session

    except errors.Unauthorized as err:
        LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired from err

    except (asyncio.TimeoutError, errors.RequestError, errors.ResponseError) as err:
        LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect from err
