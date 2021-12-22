"""Representation of a deCONZ gateway."""
import asyncio

import async_timeout
from pydeconz import DeconzSession, errors, group, light, sensor

from homeassistant.config_entries import SOURCE_HASSIO
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
    LOGGER,
    PLATFORMS,
)
from .deconz_event import async_setup_events, async_unload_events
from .errors import AuthenticationRequired, CannotConnect


@callback
def get_gateway_from_config_entry(hass, config_entry):
    """Return gateway with a matching config entry ID."""
    return hass.data[DECONZ_DOMAIN][config_entry.entry_id]


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(self, hass, config_entry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry

        self.api = None

        self.available = True
        self.ignore_state_updates = False

        self.signal_reachable = f"deconz-reachable-{config_entry.entry_id}"

        self.signal_new_group = f"deconz_new_group_{config_entry.entry_id}"
        self.signal_new_light = f"deconz_new_light_{config_entry.entry_id}"
        self.signal_new_scene = f"deconz_new_scene_{config_entry.entry_id}"
        self.signal_new_sensor = f"deconz_new_sensor_{config_entry.entry_id}"

        self.deconz_resource_type_to_signal_new_device = {
            group.RESOURCE_TYPE: self.signal_new_group,
            light.RESOURCE_TYPE: self.signal_new_light,
            group.RESOURCE_TYPE_SCENE: self.signal_new_scene,
            sensor.RESOURCE_TYPE: self.signal_new_sensor,
        }

        self.deconz_ids = {}
        self.entities = {}
        self.events = []

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

    # Callbacks

    @callback
    def async_connection_status_callback(self, available) -> None:
        """Handle signals of gateway connection status."""
        self.available = available
        self.ignore_state_updates = False
        async_dispatcher_send(self.hass, self.signal_reachable)

    @callback
    def async_add_device_callback(
        self, resource_type, device=None, force: bool = False
    ) -> None:
        """Handle event of new device creation in deCONZ."""
        if (
            not force
            and not self.option_allow_new_devices
            or resource_type not in self.deconz_resource_type_to_signal_new_device
        ):
            return

        args = []

        if device is not None and not isinstance(device, list):
            args.append([device])

        async_dispatcher_send(
            self.hass,
            self.deconz_resource_type_to_signal_new_device[resource_type],
            *args,  # Don't send device if None, it would override default value in listeners
        )

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)

        # Host device
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.api.config.mac)},
        )

        # Gateway service
        configuration_url = f"http://{self.host}:{self.config_entry.data[CONF_PORT]}"
        if self.config_entry.source == SOURCE_HASSIO:
            configuration_url = "homeassistant://hassio/ingress/core_deconz"
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

        self.hass.config_entries.async_setup_platforms(self.config_entry, PLATFORMS)

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
            self.async_add_device_callback(sensor.RESOURCE_TYPE)

        else:
            deconz_ids += [
                sensor.deconz_id
                for sensor in self.api.sensors.values()
                if sensor.type.startswith("CLIP")
            ]

        if self.option_allow_deconz_groups:
            self.async_add_device_callback(group.RESOURCE_TYPE)

        else:
            deconz_ids += [group.deconz_id for group in self.api.groups.values()]

        entity_registry = er.async_get(self.hass)

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

        await self.hass.config_entries.async_unload_platforms(
            self.config_entry, PLATFORMS
        )

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
        add_device=async_add_device_callback,
        connection_status=async_connection_status_callback,
    )
    try:
        async with async_timeout.timeout(10):
            await deconz.refresh_state()
        return deconz

    except errors.Unauthorized as err:
        LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired from err

    except (asyncio.TimeoutError, errors.RequestError) as err:
        LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect from err
