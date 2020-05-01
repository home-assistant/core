"""Code to handle a DenonAVR receiver."""
import logging

import denonavr

_LOGGER = logging.getLogger(__name__)


class ConnectDenonAVR:
    """Class to async connect to a DenonAVR receiver."""

    def __init__(self, hass):
        """Initialize the class."""
        self._hass = hass
        self._receiver = None

    @property
    def receiver(self):
        """Return the class containing all connections to the receiver."""
        return self._receiver

    async def async_connect_receiver(self, host_in, timeout_in, show_all_inputs_in, zone2, zone3):
        """Connect to the DenonAVR receiver."""
        zones = {}
        if zone2:
            zones["Zone2"] = None
        if zone3:
            zones["Zone3"] = None

        # Connect to receiver
        try:
            self._receiver = await self._hass.async_add_executor_job(
                denonavr.DenonAVR(
                    host=host_in,
                    show_all_inputs=show_all_inputs_in,
                    timeout=timeout_in,
                    add_zones=zones,
                )
            )
        except ConnectionError:
            _LOGGER.error(
                "ConnectionError during setup of denonavr with host %s", host_in
            )
            return False

        _LOGGER.debug(
            "%s receiver %s at host %s connected, model %s, serial %s",
            self._receiver.manufacturer,
            self._receiver.name,
            self._receiver.host,
            self._receiver.model_name,
            self._receiver.serial_number
        )

        return True
