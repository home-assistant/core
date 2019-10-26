"""Base class for IKEA TRADFRI."""
import asyncio
import logging
from functools import wraps

from pytradfri.error import PytradfriError, RequestTimeout

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TradfriBaseClass(Entity):
    """Base class for IKEA TRADFRI.

    All devices and groups should ultimately inherit from this class.
    """

    def __init__(self, device, api, gateway_id):
        """Initialize a device."""
        self._api = self.retry_timeout(api)  # Retry API call three times
        self._device = None
        self._device_control = None
        self._device_data = None
        self._gateway_id = gateway_id
        self._name = None
        self._unique_id = None

        self._refresh(device)

    def _restart(self, error):
        """Log error and restart observe."""
        self.async_schedule_update_ha_state()

        _LOGGER.warning(
            f"Observation failed for {self._name}, trying again",
            self._name,
            exc_info=error,
        )
        # Wait one second before trying again
        asyncio.sleep(1)
        self._async_start_observe()

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of device."""
        if exc:
            self._restart(exc)
            return

        try:
            cmd = self._device.observe(
                callback=self._observe_update,
                err_callback=self._async_start_observe,
                duration=0,
            )
            self.hass.async_create_task(self._api(cmd))
            return True
        except PytradfriError as err:
            self._restart(err)
            return False

    @staticmethod
    def retry_timeout(api, retries=3):
        """Retry API call when a timeout occurs."""

        @wraps(api)
        def retry_api(*args, **kwargs):
            """Retrying API."""
            for i in range(1, retries + 1):
                try:
                    return api(*args, **kwargs)
                except RequestTimeout:
                    if i == retries:
                        _LOGGER.warning("Request timeout")
                        raise

        return retry_api

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def name(self):
        """Return the display name of this device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for tradfri device."""
        return False

    @property
    def unique_id(self):
        """Return unique ID for device."""
        return self._unique_id

    @callback
    def _observe_update(self, device):
        """Receive new state data for this device."""
        self._refresh(device)
        self.async_schedule_update_ha_state()

    def _refresh(self, device):
        """Refresh the device data."""
        self._device = device
        self._name = device.name


class TradfriBaseDevice(TradfriBaseClass):
    """Base class for a TRADFRI device.

    All devices should inherit from this class.
    """

    def __init__(self, device, api, gateway_id):
        """Initialize a device."""
        super().__init__(device, api, gateway_id)
        self._available = True

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return the device info."""
        info = self._device.device_info

        return {
            "identifiers": {(DOMAIN, self._device.id)},
            "manufacturer": info.manufacturer,
            "model": info.model_number,
            "name": self._name,
            "sw_version": info.firmware_version,
            "via_device": (DOMAIN, self._gateway_id),
        }

    def _refresh(self, device):
        """Refresh the device data."""
        super()._refresh(device)
        self._available = device.reachable
