"""The Z-Wave-Me WS integration."""
import logging

from zwave_me_ws import ZWaveMe, ZWaveMeData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PLATFORMS, ZWAVE_PLATFORMS

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

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Create the API instance."""
        self.device_ids: list[str] = []
        self._hass = hass
        self._config = config
        self.zwave_api = ZWaveMe(
            on_device_create=self.on_device_create,
            on_device_update=self.on_device_update,
            on_new_device=self.add_device,
            token=self._config.data["token"],
            url=self._config.data["url"],
            platforms=ZWAVE_PLATFORMS,
        )

    def add_device(self, device: ZWaveMeData) -> None:
        """Send signal to create device."""
        if device.deviceType in ZWAVE_PLATFORMS:
            if device.id in self.device_ids:
                dispatcher_send(self._hass, "ZWAVE_ME_INFO_" + device.id, device)
            else:
                dispatcher_send(
                    self._hass, "ZWAVE_ME_NEW_" + device.deviceType.upper(), device
                )
                self.device_ids.append(device.id)

    def on_device_create(self, devices: list[ZWaveMeData]) -> None:
        """Create multiple devices."""
        if devices is None:
            return
        for device in devices:
            self.add_device(device)

    def on_device_update(self, new_info: ZWaveMeData) -> None:
        """Send signal to update device."""
        dispatcher_send(self._hass, "ZWAVE_ME_INFO_" + new_info.id, new_info)


class ZWaveMeEntity(Entity):
    """Representation of a ZWaveMe device."""

    def __init__(self, device):
        """Initialize the device."""
        self._attr_name = device.title
        self._attr_should_poll = False
        self.device = device

    async def async_added_to_hass(self) -> None:
        """Connect to an updater."""
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"ZWAVE_ME_INFO_{self.device.id}", self.get_new_data
        ))

    def get_device(self):
        """Get device info by id."""
        for device in self.hass.data[DOMAIN].get_devices():
            if device.id == self.device.id:
                return device

        return None

    @callback
    def get_new_data(self, new_data):
        """Update info in the HAss."""
        self.device = new_data
        self._attr_available = not new_data.isFailed
        self.async_write_ha_state

    @property
    def unique_id(self) -> str:
        """If the switch is currently on or off."""
        return DOMAIN + "." + self.device.id + self._name
