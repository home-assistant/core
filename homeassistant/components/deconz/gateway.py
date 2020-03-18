"""Representation of a deCONZ gateway."""
import asyncio

import async_timeout
from pydeconz import DeconzSession, errors

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_MASTER_GATEWAY,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DOMAIN,
    LOGGER,
    NEW_DEVICE,
    NEW_GROUP,
    NEW_SENSOR,
    SUPPORTED_PLATFORMS,
)
from .errors import AuthenticationRequired, CannotConnect


@callback
def get_gateway_from_config_entry(hass, config_entry):
    """Return gateway with a matching bridge id."""
    return hass.data[DOMAIN][config_entry.unique_id]


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(self, hass, config_entry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry

        self.available = True
        self.api = None
        self.deconz_ids = {}
        self.events = []
        self.listeners = []

        self._current_option_allow_clip_sensor = self.option_allow_clip_sensor
        self._current_option_allow_deconz_groups = self.option_allow_deconz_groups

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return self.config_entry.unique_id

    @property
    def master(self) -> bool:
        """Gateway which is used with deCONZ services without defining id."""
        return self.config_entry.options[CONF_MASTER_GATEWAY]

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

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.api.config.mac)},
            identifiers={(DOMAIN, self.api.config.bridgeid)},
            manufacturer="Dresden Elektronik",
            model=self.api.config.modelid,
            name=self.api.config.name,
            sw_version=self.api.config.swversion,
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

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception as err:  # pylint: disable=broad-except
            LOGGER.error("Error connecting with deCONZ gateway: %s", err)
            return False

        for component in SUPPORTED_PLATFORMS:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component
                )
            )

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
        if gateway.api.host != entry.data[CONF_HOST]:
            gateway.api.close()
            gateway.api.host = entry.data[CONF_HOST]
            gateway.api.start()
            return

        await gateway.options_updated()

    async def options_updated(self):
        """Manage entities affected by config entry options."""
        deconz_ids = []

        if self._current_option_allow_clip_sensor != self.option_allow_clip_sensor:
            self._current_option_allow_clip_sensor = self.option_allow_clip_sensor

            sensors = [
                sensor
                for sensor in self.api.sensors.values()
                if sensor.type.startswith("CLIP")
            ]

            if self.option_allow_clip_sensor:
                self.async_add_device_callback(NEW_SENSOR, sensors)
            else:
                deconz_ids += [sensor.deconz_id for sensor in sensors]

        if self._current_option_allow_deconz_groups != self.option_allow_deconz_groups:
            self._current_option_allow_deconz_groups = self.option_allow_deconz_groups

            groups = list(self.api.groups.values())

            if self.option_allow_deconz_groups:
                self.async_add_device_callback(NEW_GROUP, groups)
            else:
                deconz_ids += [group.deconz_id for group in groups]

        if deconz_ids:
            async_dispatcher_send(self.hass, self.signal_remove_entity, deconz_ids)

        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()

        for entity_id, deconz_id in self.deconz_ids.items():
            if deconz_id in deconz_ids and entity_registry.async_is_registered(
                entity_id
            ):
                entity_registry.async_remove(entity_id)

    @property
    def signal_reachable(self) -> str:
        """Gateway specific event to signal a change in connection status."""
        return f"deconz-reachable-{self.bridgeid}"

    @callback
    def async_connection_status_callback(self, available) -> None:
        """Handle signals of gateway connection status."""
        self.available = available
        async_dispatcher_send(self.hass, self.signal_reachable, True)

    @callback
    def async_signal_new_device(self, device_type) -> str:
        """Gateway specific event to signal new device."""
        return NEW_DEVICE[device_type].format(self.bridgeid)

    @property
    def signal_remove_entity(self) -> str:
        """Gateway specific event to signal removal of entity."""
        return f"deconz-remove-{self.bridgeid}"

    @callback
    def async_add_device_callback(self, device_type, device) -> None:
        """Handle event of new device creation in deCONZ."""
        if not isinstance(device, list):
            device = [device]
        async_dispatcher_send(
            self.hass, self.async_signal_new_device(device_type), device
        )

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

        for component in SUPPORTED_PLATFORMS:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, component
            )

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

        for event in self.events:
            event.async_will_remove_from_hass()
        self.events.clear()

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

    except errors.Unauthorized:
        LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired

    except (asyncio.TimeoutError, errors.RequestError):
        LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect
