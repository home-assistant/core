"""Support for WiLight devices."""
import ipaddress
import logging

import voluptuous as vol
from wilight import create_wilight_connection

from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_ID,
    CONF_MODE,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_ITEMS,
    CONNECTION_TIMEOUT,
    DATA_DEVICE_REGISTER,
    DEFAULT_KEEP_ALIVE_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_INTERVAL,
    DOMAIN,
    WL_TYPES,
)
from .support import (
    check_config_ex_len,
    get_item_sub_types,
    get_item_type,
    get_num_items,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("item_1"): cv.string,
        vol.Optional("item_2"): cv.string,
        vol.Optional("item_3"): cv.string,
    }
)

DEVICE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_MODE): cv.string,
        vol.Optional(CONF_ITEMS, default={}): DEVICE_ITEM_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICES): vol.All(
                    cv.ensure_list, [DEVICE_CONFIG_SCHEMA],
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the WiLight platform."""
    # Allow platform to specify function to register new unknown devices

    def add_device(device):

        num_serial = device[CONF_ID]
        device_id = f"WL{num_serial}"
        host = device[CONF_HOST]
        port = DEFAULT_PORT
        model = device[CONF_TYPE]
        config_ex = device[CONF_MODE]
        items = device[CONF_ITEMS]
        if items is None:
            items = {}

        if model not in WL_TYPES:
            _LOGGER.warning("WiLight %s with unsupported type %s", device_id, model)
            return

        if not check_config_ex_len(model, config_ex):
            _LOGGER.warning("WiLight %s with error in mode %s", device_id, config_ex)
            return

        def get_item_name(s_i):
            """Get item name."""
            item_key = f"item_{s_i}"
            if item_key in items:
                return items.get(item_key)
            return f"{device_id}_{s_i}"

        indexes = []
        item_names = []
        item_types = []
        item_sub_types = []
        num_items = get_num_items(model, config_ex)

        for i in range(1, num_items + 1):

            index = f"{i-1:01x}"
            item_name = get_item_name(f"{i:01x}")

            item_type = get_item_type(i, model, config_ex)

            item_sub_type = get_item_sub_types(i, model, config_ex)

            indexes.append(index)
            item_names.append(item_name)
            item_types.append(item_type)
            item_sub_types.append(item_sub_type)

        @callback
        def disconnected():
            # Schedule reconnect after connection has been lost.
            _LOGGER.warning("WiLight %s disconnected", device_id)
            async_dispatcher_send(hass, f"wilight_device_available_{device_id}", False)

        @callback
        def reconnected():
            # Schedule reconnect after connection has been lost.
            _LOGGER.warning("WiLight %s reconnect", device_id)
            async_dispatcher_send(hass, f"wilight_device_available_{device_id}", True)

        async def connect():
            # Set up connection and hook it into HA for reconnect/shutdown.
            _LOGGER.info("Initiating WiLight connection to %s", device_id)

            client = await create_wilight_connection(
                device_id=device_id,
                host=host,
                port=port,
                model=model,
                config_ex=config_ex,
                disconnect_callback=disconnected,
                reconnect_callback=reconnected,
                loop=hass.loop,
                timeout=CONNECTION_TIMEOUT,
                reconnect_interval=DEFAULT_RECONNECT_INTERVAL,
                keep_alive_interval=DEFAULT_KEEP_ALIVE_INTERVAL,
            )

            hass.data[DATA_DEVICE_REGISTER][device_id] = client

            # Load platforms
            hass.async_create_task(
                # (device_id, model, indexes, item_names, item_types, item_sub_types)
                # será passado para devices_from_config(hass, discovery_info)
                # em switch.py, light.py, etc
                async_load_platform(
                    hass,
                    "light",
                    DOMAIN,
                    [
                        device_id,
                        model,
                        indexes,
                        item_names,
                        item_types,
                        item_sub_types,
                    ],
                    config,
                )
            )

            hass.async_create_task(
                async_load_platform(
                    hass,
                    "switch",
                    DOMAIN,
                    [
                        device_id,
                        model,
                        indexes,
                        item_names,
                        item_types,
                        item_sub_types,
                    ],
                    config,
                )
            )

            hass.async_create_task(
                async_load_platform(
                    hass,
                    "fan",
                    DOMAIN,
                    [
                        device_id,
                        model,
                        indexes,
                        item_names,
                        item_types,
                        item_sub_types,
                    ],
                    config,
                )
            )

            hass.async_create_task(
                async_load_platform(
                    hass,
                    "cover",
                    DOMAIN,
                    [
                        device_id,
                        model,
                        indexes,
                        item_names,
                        item_types,
                        item_sub_types,
                    ],
                    config,
                )
            )

            # handle shutdown of WiLight asyncio transport
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, lambda x: client.stop()
            )

            _LOGGER.info("Connected to WiLight device: %s", device_id)

        hass.loop.create_task(connect())

    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    hass.data[DATA_DEVICE_REGISTER] = {}

    # User has configured devices
    if CONF_DEVICES not in conf:
        return True

    devices = conf[CONF_DEVICES]

    for device in devices:
        add_device(device)
    return True


class WiLightDevice(Entity):
    """Representation of a WiLight device.

    Contains the common logic for WiLight entities.
    """

    def __init__(self, item_name, index, device_id, model, item_type, client):
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._device_id = device_id
        self._index = index
        self._status = {}
        self._client = client
        self._name = item_name
        self._model = model
        self._type = item_type
        self._unique_id = self._device_id + self._index

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
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._client.is_connected)
