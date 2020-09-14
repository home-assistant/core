"""Code to handle a DenonAVR receiver."""
import logging

import denonavr

_LOGGER = logging.getLogger(__name__)


class ConnectDenonAVR:
    """Class to async connect to a DenonAVR receiver."""

    def __init__(self, hass, host, timeout, show_all_inputs, zone2, zone3):
        """Initialize the class."""
        self._hass = hass
        self._receiver = None
        self._host = host
        self._show_all_inputs = show_all_inputs
        self._timeout = timeout

        self._zones = {}
        if zone2:
            self._zones["Zone2"] = None
        if zone3:
            self._zones["Zone3"] = None

    @property
    def receiver(self):
        """Return the class containing all connections to the receiver."""
        return self._receiver

    async def async_connect_receiver(self):
        """Connect to the DenonAVR receiver."""
        if not await self._hass.async_add_executor_job(self.init_receiver_class):
            return False

        if (
            self._receiver.manufacturer is None
            or self._receiver.name is None
            or self._receiver.model_name is None
            or self._receiver.receiver_type is None
        ):
            _LOGGER.error(
                "Missing receiver information: manufacturer '%s', name '%s', model '%s', type '%s'",
                self._receiver.manufacturer,
                self._receiver.name,
                self._receiver.model_name,
                self._receiver.receiver_type,
            )
            return False

        _LOGGER.debug(
            "%s receiver %s at host %s connected, model %s, serial %s, type %s",
            self._receiver.manufacturer,
            self._receiver.name,
            self._receiver.host,
            self._receiver.model_name,
            self._receiver.serial_number,
            self._receiver.receiver_type,
        )

        return True

    def init_receiver_class(self):
        """Initialize the DenonAVR class in a way that can called by async_add_executor_job."""
        try:
            self._receiver = denonavr.DenonAVR(
                host=self._host,
                show_all_inputs=self._show_all_inputs,
                timeout=self._timeout,
                add_zones=self._zones,
            )
        except ConnectionError:
            _LOGGER.error(
                "ConnectionError during setup of denonavr with host %s", self._host
            )
            return False

        return True
