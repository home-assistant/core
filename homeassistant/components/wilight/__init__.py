"""The WiLight integration."""
import asyncio
import logging

import pywilight
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, DT_CONFIG, DT_PENDING, DT_REGISTRY, DT_SERIAL

_LOGGER = logging.getLogger(__name__)


def coerce_host_port(value):
    """Validate that provided value is either just host or host:port.

    Returns (host, None) or (host, port) respectively.
    """
    host, _, port = value.partition(":")

    if not host:
        raise vol.Invalid("host cannot be empty")

    if port:
        port = cv.port(port)
    else:
        port = None

    return host, port


CONF_STATIC = "static"
CONF_DISCOVERY = "discovery"

DEFAULT_DISCOVERY = True

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_STATIC, default=[]): vol.Schema(
                    [vol.All(cv.string, coerce_host_port)]
                ),
                vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the WiLight with Config Flow component."""

    hass.data[DOMAIN] = {
        DT_CONFIG: config.get(DOMAIN, {}),
        DT_REGISTRY: {},
        DT_PENDING: {},
        DT_SERIAL: [],
    }

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a wilight config entry."""

    config = hass.data[DOMAIN].pop(DT_CONFIG)

    # Keep track of WiLight device subscriptions for client updates
    hass.data[DOMAIN][DT_REGISTRY] = pywilight.SubscriptionRegistry()

    devices = {}

    static_conf = config.get(CONF_STATIC, [])
    if static_conf:
        _LOGGER.debug("Adding statically configured WiLight devices...")
        for device in await asyncio.gather(
            *[
                hass.async_add_executor_job(validate_static_config, host, port)
                for host, port in static_conf
            ]
        ):
            if device is None:
                continue

            devices.setdefault(device.serial_number, device)

    if config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY):
        _LOGGER.debug("Scanning network for WiLight devices...")
        for device in await hass.async_add_executor_job(pywilight.discover_devices):
            devices.setdefault(
                device.serial_number, device,
            )

    loaded_components = set()

    def add_device(hass, device):

        if device.serial_number in hass.data[DOMAIN][DT_SERIAL]:
            _LOGGER.debug(
                "Existing WiLight device %s (%s)", device.host, device.serial_number,
            )
            return

        hass.data[DOMAIN][DT_SERIAL].append(device.serial_number)

        @callback
        def client_created_callback(device, type_, params):
            # Callback to continue device setup after creating the client.
            hass.add_job(dispatch_devices_callback(device))

        registry = hass.data[DOMAIN][DT_REGISTRY]
        registry.on(device, "created", client_created_callback)

        @callback
        def disconnected():
            # Schedule reconnect after connection has been lost.
            _LOGGER.warning("WiLight %s disconnected", device.device_id)
            async_dispatcher_send(
                hass, f"wilight_device_available_{device.device_id}", False
            )

        @callback
        def reconnected():
            # Schedule reconnect after connection has been lost.
            _LOGGER.warning("WiLight %s reconnect", device.device_id)
            async_dispatcher_send(
                hass, f"wilight_device_available_{device.device_id}", True
            )

        async def connect(device):
            # Set up connection and hook it into HA for reconnect/shutdown.
            _LOGGER.info("Initiating WiLight connection to %s", device.device_id)

            client = await device.config_client(
                disconnect_callback=disconnected,
                reconnect_callback=reconnected,
                loop=asyncio.get_running_loop(),
                logger=_LOGGER,
            )

            # handle shutdown of WiLight asyncio transport
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, lambda x: client.stop()
            )

            _LOGGER.info("Connected to WiLight device: %s", device.device_id)

            # Sending event that the client is created
            registry = hass.data[DOMAIN][DT_REGISTRY]
            registry.event(device, "created", None)

        # hass.loop.create_task(connect(device))
        asyncio.get_running_loop().create_task(connect(device))
        # hass.async_create_task(connect(device))

    def dispatch_devices(hass, device):

        for component in PLATFORMS:

            # Three cases:
            # - First time we see component, we need to load it and initialize the backlog
            # - Component is being loaded, add to backlog
            # - Component is loaded, backlog is gone, dispatch discovery

            if component not in loaded_components:
                hass.data[DOMAIN][DT_PENDING][component] = [device]
                loaded_components.add(component)
                hass.async_create_task(
                    hass.config_entries.async_forward_entry_setup(entry, component)
                )

            elif component in hass.data[DOMAIN][DT_PENDING]:
                hass.data[DOMAIN][DT_PENDING][component].append(device)

            else:
                async_dispatcher_send(hass, f"{DOMAIN}.{component}", hass, device)

    for device in devices.values():
        add_device(hass, device)

    @callback
    async def dispatch_devices_callback(device):
        dispatch_devices(hass, device)

    return True


def validate_static_config(host, port):
    """Handle a static config."""
    url = f"http://{host}:45995/wilight.xml"

    if not url:
        _LOGGER.error(
            "Unable to get description url for WiLight at: %s", f"{host}",
        )
        return None

    try:
        device = pywilight.discovery.device_from_description(url, None)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,) as err:
        _LOGGER.error("Unable to access WiLight at %s (%s)", url, err)
        return None

    return device


class WiLightDevice(Entity):
    """Representation of a WiLight device.

    Contains the common logic for WiLight entities.
    """

    def __init__(self, wilight, index, item_name, item_type):
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._wilight = wilight
        self._device_id = wilight.device_id
        self._swversion = wilight.swversion
        self._client = wilight.client
        self._model = wilight.model
        self._name = item_name
        self._index = index
        self._type = item_type
        self._unique_id = self._device_id + self._index
        self._status = {}

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return a name for this WiLight item."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this WiLight item."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._unique_id)},
            "model": self._model,
            "manufacturer": "WiLight",
            "sw_version": self._swversion,
            "via_device": (DOMAIN, self._device_id),
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def handle_event_callback(self, states):
        """Propagate changes through ha."""
        self._status = states
        self.async_write_ha_state()

    async def async_update(self):
        """Synchronize state with bridge."""
        await self._client.status(self._index)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )
