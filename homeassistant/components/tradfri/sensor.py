"""Support for IKEA Tradfri sensors."""
from datetime import timedelta
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import KEY_API, KEY_GATEWAY

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Tradfri config entry."""
    api = hass.data[KEY_API][config_entry.entry_id]
    gateway = hass.data[KEY_GATEWAY][config_entry.entry_id]

    devices_commands = await api(gateway.get_devices())
    all_devices = await api(devices_commands)
    devices = (dev for dev in all_devices if not dev.has_light_control and
               not dev.has_socket_control)
    async_add_entities(TradfriDevice(device, api) for device in devices)


class TradfriDevice(Entity):
    """The platform class required by Home Assistant."""

    def __init__(self, device, api):
        """Initialize the device."""
        self._api = api
        self._device = None
        self._name = None

        self._refresh(device)

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def should_poll(self):
        """No polling needed for tradfri."""
        return False

    @property
    def name(self):
        """Return the display name of this device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return '%'

    @property
    def device_state_attributes(self):
        """Return the devices' state attributes."""
        info = self._device.device_info
        attrs = {
            'manufacturer': info.manufacturer,
            'model_number': info.model_number,
            'serial': info.serial,
            'firmware_version': info.firmware_version,
            'power_source': info.power_source_str,
            'battery_level': info.battery_level
        }
        return attrs

    @property
    def state(self):
        """Return the current state of the device."""
        return self._device.device_info.battery_level

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of light."""
        # pylint: disable=import-error
        from pytradfri.error import PytradfriError
        if exc:
            _LOGGER.warning("Observation failed for %s", self._name,
                            exc_info=exc)

        try:
            cmd = self._device.observe(callback=self._observe_update,
                                       err_callback=self._async_start_observe,
                                       duration=0)
            self.hass.async_create_task(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    def _refresh(self, device):
        """Refresh the device data."""
        self._device = device
        self._name = device.name

    def _observe_update(self, tradfri_device):
        """Receive new state data for this device."""
        self._refresh(tradfri_device)

        self.hass.async_create_task(self.async_update_ha_state())
