"""Support for Tellstick."""
import logging
import threading

from tellcore.constants import (
    TELLSTICK_DIM,
    TELLSTICK_TURNOFF,
    TELLSTICK_TURNON,
    TELLSTICK_UP,
)
from tellcore.library import TelldusError
from tellcore.telldus import AsyncioCallbackDispatcher, TelldusCore
from tellcorenet import TellCoreClient
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ATTR_DISCOVER_CONFIG = "config"
ATTR_DISCOVER_DEVICES = "devices"
CONF_SIGNAL_REPETITIONS = "signal_repetitions"

DEFAULT_SIGNAL_REPETITIONS = 1
DOMAIN = "tellstick"

DATA_TELLSTICK = "tellstick_device"
SIGNAL_TELLCORE_CALLBACK = "tellstick_callback"

# Use a global tellstick domain lock to avoid getting Tellcore errors when
# calling concurrently.
TELLSTICK_LOCK = threading.RLock()

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

    _LOGGER.info(
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


class TellstickDevice(Entity):
    """Representation of a Tellstick device.

    Contains the common logic for all Tellstick devices.
    """

    _attr_assumed_state = True
    _attr_should_poll = False

    def __init__(self, tellcore_device, signal_repetitions):
        """Init the Tellstick device."""
        self._signal_repetitions = signal_repetitions
        self._state = None
        self._requested_state = None
        self._requested_data = None
        self._repeats_left = 0

        # Look up our corresponding tellcore device
        self._tellcore_device = tellcore_device
        self._attr_name = tellcore_device.name
        self._attr_unique_id = tellcore_device.id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_TELLCORE_CALLBACK, self.update_from_callback
            )
        )

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._state

    def _parse_ha_data(self, kwargs):
        """Turn the value from HA into something useful."""
        raise NotImplementedError

    def _parse_tellcore_data(self, tellcore_data):
        """Turn the value received from tellcore into something useful."""
        raise NotImplementedError

    def _update_model(self, new_state, data):
        """Update the device entity state to match the arguments."""
        raise NotImplementedError

    def _send_device_command(self, requested_state, requested_data):
        """Let tellcore update the actual device to the requested state."""
        raise NotImplementedError

    def _send_repeated_command(self):
        """Send a tellstick command once and decrease the repeat count."""

        with TELLSTICK_LOCK:
            if self._repeats_left > 0:
                self._repeats_left -= 1
                try:
                    self._send_device_command(
                        self._requested_state, self._requested_data
                    )
                except TelldusError as err:
                    _LOGGER.error(err)

    def _change_device_state(self, new_state, data):
        """Turn on or off the device."""
        with TELLSTICK_LOCK:
            # Set the requested state and number of repeats before calling
            # _send_repeated_command the first time. Subsequent calls will be
            # made from the callback. (We don't want to queue a lot of commands
            # in case the user toggles the switch the other way before the
            # queue is fully processed.)
            self._requested_state = new_state
            self._requested_data = data
            self._repeats_left = self._signal_repetitions
            self._send_repeated_command()

            # Sooner or later this will propagate to the model from the
            # callback, but for a fluid UI experience update it directly.
            self._update_model(new_state, data)
            self.schedule_update_ha_state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._change_device_state(True, self._parse_ha_data(kwargs))

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._change_device_state(False, None)

    def _update_model_from_command(self, tellcore_command, tellcore_data):
        """Update the model, from a sent tellcore command and data."""

        if tellcore_command not in [TELLSTICK_TURNON, TELLSTICK_TURNOFF, TELLSTICK_DIM]:
            _LOGGER.debug("Unhandled tellstick command: %d", tellcore_command)
            return

        self._update_model(
            tellcore_command != TELLSTICK_TURNOFF,
            self._parse_tellcore_data(tellcore_data),
        )

    def update_from_callback(self, tellcore_id, tellcore_command, tellcore_data):
        """Handle updates from the tellcore callback."""
        if tellcore_id != self._tellcore_device.id:
            return

        self._update_model_from_command(tellcore_command, tellcore_data)
        self.schedule_update_ha_state()

        # This is a benign race on _repeats_left -- it's checked with the lock
        # in _send_repeated_command.
        if self._repeats_left > 0:
            self._send_repeated_command()

    def _update_from_tellcore(self):
        """Read the current state of the device from the tellcore library."""

        with TELLSTICK_LOCK:
            try:
                last_command = self._tellcore_device.last_sent_command(
                    TELLSTICK_TURNON | TELLSTICK_TURNOFF | TELLSTICK_DIM
                )
                last_data = self._tellcore_device.last_sent_value()
                self._update_model_from_command(last_command, last_data)
            except TelldusError as err:
                _LOGGER.error(err)

    def update(self):
        """Poll the current state of the device."""
        self._update_from_tellcore()
