"""Support for Tellstick."""

import logging

from tellcore.constants import TELLSTICK_DIM, TELLSTICK_UP
from tellcore.telldus import AsyncioCallbackDispatcher, TelldusCore
from tellcorenet import TellCoreClient
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DISCOVER_CONFIG,
    ATTR_DISCOVER_DEVICES,
    DATA_TELLSTICK,
    DEFAULT_SIGNAL_REPETITIONS,
    SIGNAL_TELLCORE_CALLBACK,
)

_LOGGER = logging.getLogger(__name__)

CONF_SIGNAL_REPETITIONS = "signal_repetitions"

DOMAIN = "tellstick"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Inclusive(CONF_HOST, "tellcore-net"): cv.string,
                vol.Inclusive(CONF_PORT, "tellcore-net"): vol.All(
                    cv.ensure_list, [cv.port], vol.Length(min=2, max=2)
                ),
                vol.Optional(
                    CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS
                ): vol.Coerce(int),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _discover(hass, config, component_name, found_tellcore_devices):
    """Set up and send the discovery event."""
    if not found_tellcore_devices:
        return

    _LOGGER.debug(
        "Discovered %d new %s devices", len(found_tellcore_devices), component_name
    )

    signal_repetitions = config[DOMAIN].get(CONF_SIGNAL_REPETITIONS)

    discovery.load_platform(
        hass,
        component_name,
        DOMAIN,
        {
            ATTR_DISCOVER_DEVICES: found_tellcore_devices,
            ATTR_DISCOVER_CONFIG: signal_repetitions,
        },
        config,
    )


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tellstick component."""

    conf = config.get(DOMAIN, {})
    net_host = conf.get(CONF_HOST)
    net_ports = conf.get(CONF_PORT)

    # Initialize remote tellcore client
    if net_host:
        net_client = TellCoreClient(
            host=net_host, port_client=net_ports[0], port_events=net_ports[1]
        )
        net_client.start()

        def stop_tellcore_net(event):
            """Event handler to stop the client."""
            net_client.stop()

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_tellcore_net)

    try:
        tellcore_lib = TelldusCore(
            callback_dispatcher=AsyncioCallbackDispatcher(hass.loop)
        )
    except OSError:
        _LOGGER.exception("Could not initialize Tellstick")
        return False

    # Get all devices, switches and lights alike
    tellcore_devices = tellcore_lib.devices()

    # Register devices
    hass.data[DATA_TELLSTICK] = {device.id: device for device in tellcore_devices}

    # Discover the lights
    _discover(
        hass,
        config,
        "light",
        [device.id for device in tellcore_devices if device.methods(TELLSTICK_DIM)],
    )

    # Discover the cover
    _discover(
        hass,
        config,
        "cover",
        [device.id for device in tellcore_devices if device.methods(TELLSTICK_UP)],
    )

    # Discover the switches
    _discover(
        hass,
        config,
        "switch",
        [
            device.id
            for device in tellcore_devices
            if (not device.methods(TELLSTICK_UP) and not device.methods(TELLSTICK_DIM))
        ],
    )

    @callback
    def async_handle_callback(tellcore_id, tellcore_command, tellcore_data, cid):
        """Handle the actual callback from Tellcore."""
        async_dispatcher_send(
            hass, SIGNAL_TELLCORE_CALLBACK, tellcore_id, tellcore_command, tellcore_data
        )

    # Register callback
    callback_id = tellcore_lib.register_device_event(async_handle_callback)

    def clean_up_callback(event):
        """Unregister the callback bindings."""
        if callback_id is not None:
            tellcore_lib.unregister_callback(callback_id)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, clean_up_callback)

    return True
