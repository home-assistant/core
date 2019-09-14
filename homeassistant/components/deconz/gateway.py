"""Representation of a deCONZ gateway."""
import asyncio
import async_timeout

from pydeconz import DeconzSession, errors

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import (
    async_get_registry,
    DISABLED_CONFIG_ENTRY,
)

from .const import (
    _LOGGER,
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_BRIDGEID,
    CONF_MASTER_GATEWAY,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DOMAIN,
    NEW_DEVICE,
    SUPPORTED_PLATFORMS,
)

from .errors import AuthenticationRequired, CannotConnect


@callback
def get_gateway_from_config_entry(hass, config_entry):
    """Return gateway with a matching bridge id."""
    return hass.data[DOMAIN][config_entry.data[CONF_BRIDGEID]]


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None

        self.deconz_ids = {}
        self.events = []
        self.listeners = []

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return self.config_entry.data[CONF_BRIDGEID]

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

    async def async_update_device_registry(self):
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

    async def async_setup(self):
        """Set up a deCONZ gateway."""
        hass = self.hass

        try:
            self.api = await get_gateway(
                hass,
                self.config_entry.data,
                self.async_add_device_callback,
                self.async_connection_status_callback,
            )

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("Error connecting with deCONZ gateway")
            return False

        for component in SUPPORTED_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component
                )
            )

        self.api.start()

        self.config_entry.add_update_listener(self.async_new_address)
        self.config_entry.add_update_listener(self.async_options_updated)

        return True

    @staticmethod
    async def async_new_address(hass, entry):
        """Handle signals of gateway getting new address.

        This is a static method because a class method (bound method),
        can not be used with weak references.
        """
        gateway = get_gateway_from_config_entry(hass, entry)
        if gateway.api.host != entry.data[CONF_HOST]:
            gateway.api.close()
            gateway.api.host = entry.data[CONF_HOST]
            gateway.api.start()

    @property
    def signal_reachable(self):
        """Gateway specific event to signal a change in connection status."""
        return f"deconz-reachable-{self.bridgeid}"

    @callback
    def async_connection_status_callback(self, available):
        """Handle signals of gateway connection status."""
        self.available = available
        async_dispatcher_send(self.hass, self.signal_reachable, True)

    @property
    def signal_options_update(self):
        """Event specific per deCONZ entry to signal new options."""
        return f"deconz-options-{self.bridgeid}"

    @staticmethod
    async def async_options_updated(hass, entry):
        """Triggered by config entry options updates."""
        gateway = get_gateway_from_config_entry(hass, entry)

        registry = await async_get_registry(hass)
        async_dispatcher_send(hass, gateway.signal_options_update, registry)

    @callback
    def async_signal_new_device(self, device_type):
        """Gateway specific event to signal new device."""
        return NEW_DEVICE[device_type].format(self.bridgeid)

    @callback
    def async_add_device_callback(self, device_type, device):
        """Handle event of new device creation in deCONZ."""
        if not isinstance(device, list):
            device = [device]
        async_dispatcher_send(
            self.hass, self.async_signal_new_device(device_type), device
        )

    @callback
    def shutdown(self, event):
        """Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.close()

    async def async_reset(self):
        """Reset this gateway to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
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
            self.events.remove(event)

        self.deconz_ids = {}
        return True


async def get_gateway(
    hass, config, async_add_device_callback, async_connection_status_callback
):
    """Create a gateway object and verify configuration."""
    session = aiohttp_client.async_get_clientsession(hass)

    deconz = DeconzSession(
        hass.loop,
        session,
        **config,
        async_add_device=async_add_device_callback,
        connection_status=async_connection_status_callback,
    )
    try:
        with async_timeout.timeout(10):
            await deconz.async_load_parameters()
        return deconz

    except errors.Unauthorized:
        _LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired

    except (asyncio.TimeoutError, errors.RequestError):
        _LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect


class DeconzEntityHandler:
    """Platform entity handler to help with updating disabled by."""

    def __init__(self, gateway):
        """Create an entity handler."""
        self.gateway = gateway
        self._entities = []

        gateway.listeners.append(
            async_dispatcher_connect(
                gateway.hass, gateway.signal_options_update, self.update_entity_registry
            )
        )

    @callback
    def add_entity(self, entity):
        """Add a new entity to handler."""
        self._entities.append(entity)

    @callback
    def update_entity_registry(self, entity_registry):
        """Update entity registry disabled by status."""
        for entity in self._entities:

            if entity.entity_registry_enabled_default != entity.enabled:
                disabled_by = None

                if entity.enabled:
                    disabled_by = DISABLED_CONFIG_ENTRY

                entity_registry.async_update_entity(
                    entity.registry_entry.entity_id, disabled_by=disabled_by
                )
