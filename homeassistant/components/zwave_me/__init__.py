"""The Z-Wave-Me WS integration."""
import asyncio
import logging

from zwave_me_ws import ZWaveMe, ZWaveMeData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, PLATFORMS, ZWaveMePlatform

_LOGGER = logging.getLogger(__name__)
ZWAVE_ME_PLATFORMS = [platform.value for platform in ZWaveMePlatform]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Z-Wave-Me from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    controller = hass.data[DOMAIN][entry.entry_id] = ZWaveMeController(hass, entry)
    if await controller.async_establish_connection():
        hass.async_create_task(async_setup_platforms(hass, entry, controller))
        return True
    raise ConfigEntryNotReady()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        controller = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.zwave_api.close_ws()
    return unload_ok


class ZWaveMeController:
    """Main ZWave-Me API class."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Create the API instance."""
        self.device_ids: set = set()
        self._hass = hass
        self.config = config
        self.zwave_api = ZWaveMe(
            on_device_create=self.on_device_create,
            on_device_update=self.on_device_update,
            on_new_device=self.add_device,
            token=self.config.data[CONF_TOKEN],
            url=self.config.data[CONF_URL],
            platforms=ZWAVE_ME_PLATFORMS,
        )
        self.platforms_inited = False

    async def async_establish_connection(self):
        """Get connection status."""
        is_connected = await self.zwave_api.get_connection()
        return is_connected

    def add_device(self, device: ZWaveMeData) -> None:
        """Send signal to create device."""
        if device.deviceType in ZWAVE_ME_PLATFORMS and self.platforms_inited:
            if device.id in self.device_ids:
                dispatcher_send(self._hass, f"ZWAVE_ME_INFO_{device.id}", device)
            else:
                dispatcher_send(
                    self._hass, f"ZWAVE_ME_NEW_{device.deviceType.upper()}", device
                )
                self.device_ids.add(device.id)

    def on_device_create(self, devices: list) -> None:
        """Create multiple devices."""
        for device in devices:
            self.add_device(device)

    def on_device_update(self, new_info: ZWaveMeData) -> None:
        """Send signal to update device."""
        dispatcher_send(self._hass, f"ZWAVE_ME_INFO_{new_info.id}", new_info)


async def async_setup_platforms(
    hass: HomeAssistant, entry: ConfigEntry, controller: ZWaveMeController
) -> None:
    """Set up platforms."""
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_setup(entry, platform)
            for platform in PLATFORMS
        ]
    )
    controller.platforms_inited = True

    await hass.async_add_executor_job(controller.zwave_api.get_devices)


class ZWaveMeEntity(Entity):
    """Representation of a ZWaveMe device."""

    def __init__(self, controller, device):
        """Initialize the device."""
        self.controller = controller
        self.device = device
        self._attr_name = device.title
        self._attr_unique_id: str = (
            f"{self.controller.config.unique_id}-{self.device.id}"
        )
        self._attr_should_poll = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._attr_name,
            manufacturer=self.device.manufacturer,
            sw_version=self.device.firmware,
            suggested_area=self.device.locationName,
        )

    async def async_added_to_hass(self) -> None:
        """Connect to an updater."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"ZWAVE_ME_INFO_{self.device.id}", self.get_new_data
            )
        )

    @callback
    def get_new_data(self, new_data):
        """Update info in the HAss."""
        self.device = new_data
        self._attr_available = not new_data.isFailed
        self.async_write_ha_state()
