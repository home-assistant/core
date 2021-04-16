"""Representation of a deCONZ gateway."""
import asyncio

import async_timeout
from pydeconz import DeconzSession, errors

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
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
    LOGGER,
    NEW_GROUP,
    NEW_LIGHT,
    NEW_SCENE,
    NEW_SENSOR,
    PLATFORMS,
)
from .deconz_event import async_setup_events, async_unload_events
from .errors import AuthenticationRequired, CannotConnect


@callback
def get_gateway_from_config_entry(hass, config_entry):
    """Return gateway with a matching bridge id."""
    return hass.data[DECONZ_DOMAIN][config_entry.unique_id]


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(self, hass, config_entry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry

        self.api = None

        self.available = True
        self.ignore_state_updates = False

        self.deconz_ids = {}
        self.entities = {}
        self.events = []
        self.listeners = []

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return self.config_entry.unique_id

    @property
    def host(self) -> str:
        """Return the host of the gateway."""
        return self.config_entry.data[CONF_HOST]

    @property
    def master(self) -> bool:
        """Gateway which is used with deCONZ services without defining id."""
        return self.config_entry.options[CONF_MASTER_GATEWAY]

    # Options

    @property
    def option_allow_clip_sensor(self) -> bool:
        """Allow loading clip sensor from gateway."""
        return self.config_entry.options.get(
            CONF_ALLOW_CLIP_SENSOR, DEFAULT_ALLOW_CLIP_SENSOR
        )

    @property
    def option_allow_deconz_groups(self) -> bool:
        """Allow loading deCONZ groups from gateway."""
        return self.config_entry.options.get(
            CONF_ALLOW_DECONZ_GROUPS, DEFAULT_ALLOW_DECONZ_GROUPS
        )

    @property
    def option_allow_new_devices(self) -> bool:
        """Allow automatic adding of new devices."""
        return self.config_entry.options.get(
            CONF_ALLOW_NEW_DEVICES, DEFAULT_ALLOW_NEW_DEVICES
        )

    # Signals

    @property
    def signal_reachable(self) -> str:
        """Gateway specific event to signal a change in connection status."""
        return f"deconz-reachable-{self.bridgeid}"

    @callback
    def async_signal_new_device(self, device_type) -> str:
        """Gateway specific event to signal new device."""
        new_device = {
            NEW_GROUP: f"deconz_new_group_{self.bridgeid}",
            NEW_LIGHT: f"deconz_new_light_{self.bridgeid}",
            NEW_SCENE: f"deconz_new_scene_{self.bridgeid}",
            NEW_SENSOR: f"deconz_new_sensor_{self.bridgeid}",
        }
        return new_device[device_type]

    # Callbacks

    @callback
    def async_connection_status_callback(self, available) -> None:
        """Handle signals of gateway connection status."""
        self.available = available
        self.ignore_state_updates = False
        async_dispatcher_send(self.hass, self.signal_reachable, True)

    @callback
    def async_add_device_callback(
        self, device_type, device=None, force: bool = False
    ) -> None:
        """Handle event of new device creation in deCONZ."""
        if not force and not self.option_allow_new_devices:
            return

        args = []

        if device is not None and not isinstance(device, list):
            args.append([device])

        async_dispatcher_send(
            self.hass,
            self.async_signal_new_device(device_type),
            *args,  # Don't send device if None, it would override default value in listeners
        )

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()

        # Host device
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.api.config.mac)},
        )

        # Gateway service
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DECONZ_DOMAIN, self.api.config.bridgeid)},
            manufacturer="Dresden Elektronik",
            model=self.api.config.modelid,
            name=self.api.config.name,
            sw_version=self.api.config.swversion,
            via_device=(CONNECTION_NETWORK_MAC, self.api.config.mac),
        )

    async def async_setup(self) -> bool:
        """Set up a deCONZ gateway."""
        try:
            self.api = await get_gateway(
                self.hass,
                self.config_entry.data,
                self.async_add_device_callback,
                self.async_connection_status_callback,
            )

        except CannotConnect as err:
            raise ConfigEntryNotReady from err

        except AuthenticationRequired as err:
            raise ConfigEntryAuthFailed from err

        for platform in PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, platform
                )
            )

        await async_setup_events(self)

        self.api.start()

        self.config_entry.add_update_listener(self.async_config_entry_updated)

        return True

    @staticmethod
    async def async_config_entry_updated(hass, entry) -> None:
        """Handle signals of config entry being updated.

        This is a static method because a class method (bound method), can not be used with weak references.
        Causes for this is either discovery updating host address or config entry options changing.
        """
        gateway = get_gateway_from_config_entry(hass, entry)

        if gateway.api.host != gateway.host:
            gateway.api.close()
            gateway.api.host = gateway.host
            gateway.api.start()
            return

        await gateway.options_updated()

    async def options_updated(self):
        """Manage entities affected by config entry options."""
        deconz_ids = []

        if self.option_allow_clip_sensor:
            self.async_add_device_callback(NEW_SENSOR)

        else:
            deconz_ids += [
                sensor.deconz_id
                for sensor in self.api.sensors.values()
                if sensor.type.startswith("CLIP")
            ]

        if self.option_allow_deconz_groups:
            self.async_add_device_callback(NEW_GROUP)

        else:
            deconz_ids += [group.deconz_id for group in self.api.groups.values()]

        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()

        for entity_id, deconz_id in self.deconz_ids.items():
            if deconz_id in deconz_ids and entity_registry.async_is_registered(
                entity_id
            ):
                # Removing an entity from the entity registry will also remove them
                # from Home Assistant
                entity_registry.async_remove(entity_id)

    @callback
    def shutdown(self, event) -> None:
        """Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.close()

    async def async_reset(self):
        """Reset this gateway to default state."""
        self.api.async_connection_status_callback = None
        self.api.close()

        for platform in PLATFORMS:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, platform
            )

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

        async_unload_events(self)

        self.deconz_ids = {}
        return True


async def get_gateway(
    hass, config, async_add_device_callback, async_connection_status_callback
) -> DeconzSession:
    """Create a gateway object and verify configuration."""
    session = aiohttp_client.async_get_clientsession(hass)

    deconz = DeconzSession(
        session,
        config[CONF_HOST],
        config[CONF_PORT],
        config[CONF_API_KEY],
        async_add_device=async_add_device_callback,
        connection_status=async_connection_status_callback,
    )
    try:
        with async_timeout.timeout(10):
            await deconz.initialize()
        return deconz

    except errors.Unauthorized as err:
        LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired from err

    except (asyncio.TimeoutError, errors.RequestError) as err:
        LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect from err
