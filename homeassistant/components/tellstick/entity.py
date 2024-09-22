"""Support for Tellstick."""

import logging
import threading

from tellcore.constants import TELLSTICK_DIM, TELLSTICK_TURNOFF, TELLSTICK_TURNON
from tellcore.library import TelldusError

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_TELLCORE_CALLBACK

_LOGGER = logging.getLogger(__name__)

# Use a global tellstick domain lock to avoid getting Tellcore errors when
# calling concurrently.
TELLSTICK_LOCK = threading.RLock()


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
