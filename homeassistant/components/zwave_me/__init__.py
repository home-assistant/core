"""The Z-Wave-Me WS integration."""
import logging

from zwave_me_ws import ZWaveMe, ZWaveMeData

from homeassistant.helpers.entity import Entity
from .const import (
    DOMAIN,
    PLATFORMS,
    ZWAVEPLATFORMS,
)
from homeassistant.helpers.dispatcher import dispatcher_send, async_dispatcher_connect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up Z-Wave-Me from a config entry."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    hass.data[DOMAIN] = ZWaveMeController(hass, entry)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class ZWaveMeController:
    """Main ZWave-Me API class."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry):
        """Create the API instance."""
        self.device_ids = []
        self._hass = hass
        self._config = config
        self.zwave_api = ZWaveMe(
            on_device_create=self.on_device_create,
            on_device_update=self.on_device_update,
            on_new_device=self.add_device,
            token=self._config.data["token"],
            url=self._config.data["url"],
            platforms=ZWAVEPLATFORMS,
        )

    def add_device(self, device: ZWaveMeData):
        """Send signal to create device."""
        if device.deviceType in ZWAVEPLATFORMS:
            if device.id in self.device_ids:
                dispatcher_send(self._hass, "ZWAVE_ME_INFO_" + device.id, device)
            else:
                dispatcher_send(
                    self._hass, "ZWAVE_ME_NEW_" + device.deviceType.upper(), device
                )
                self.device_ids.append(device.id)

    def on_device_create(self, devices: list[ZWaveMeData]):
        """Create multiple devices."""
        for device in devices:
            self.add_device(device)

    def on_device_update(self, new_info: ZWaveMeData):
        """Send signal to update device."""
        dispatcher_send(self._hass, "ZWAVE_ME_INFO_" + new_info.id, new_info)


class ZWaveMeDevice(Entity):
    """Representation of a ZWaveMe device."""

    def __init__(self, device):
        """Initialize the device."""
        self._name = device.title
        self._outlet = None
        self.device = device

    async def async_added_to_hass(self) -> None:
        """Connect to an updater."""
        async_dispatcher_connect(
            self.hass, "ZWAVE_ME_INFO_" + self.device.id, self.get_new_data
        )

    def get_device(self):
        """Get device info by id."""
        for device in self.hass.data[DOMAIN].get_devices():
            if device.id == self.device.id:
                return device

        return None

    def get_new_data(self, new_data):
        """Update info in the HAss."""
        self.device = new_data
        self.schedule_update_ha_state()

    def get_available(self):
        """Get availability of a generic device."""
        return not self.device.isFailed

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return true if device is online."""
        return self.get_available()

    def update(self):
        """Update device state."""
        pass

    @property
    def unique_id(self) -> str:
        """If the switch is currently on or off."""
        return DOMAIN + "." + self.device.id + self._name
