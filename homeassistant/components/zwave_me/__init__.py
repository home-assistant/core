"""The Z-Wave-Me WS integration."""

import logging

from zwave_me_ws import ZWaveMe, ZWaveMeData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PLATFORMS, ZWaveMePlatform

_LOGGER = logging.getLogger(__name__)
ZWAVE_ME_PLATFORMS = [platform.value for platform in ZWaveMePlatform]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Z-Wave-Me from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    controller = hass.data[DOMAIN][entry.entry_id] = ZWaveMeController(hass, entry)
    if await controller.async_establish_connection():
        await async_setup_platforms(hass, entry, controller)
        registry = dr.async_get(hass)
        controller.remove_stale_devices(registry)
        return True
    raise ConfigEntryNotReady


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
            on_device_remove=self.on_device_unavailable,
            on_device_destroy=self.on_device_destroy,
            on_new_device=self.add_device,
            token=self.config.data[CONF_TOKEN],
            url=self.config.data[CONF_URL],
            platforms=ZWAVE_ME_PLATFORMS,
        )
        self.platforms_inited = False

    async def async_establish_connection(self):
        """Get connection status."""
        return await self.zwave_api.get_connection()

    def add_device(self, device: ZWaveMeData) -> None:
        """Send signal to create device."""
        if device.id in self.device_ids:
            dispatcher_send(self._hass, f"ZWAVE_ME_INFO_{device.id}", device)
        else:
            dispatcher_send(
                self._hass, f"ZWAVE_ME_NEW_{device.deviceType.upper()}", device
            )
            self.device_ids.add(device.id)

    def on_device_create(self, devices: list[ZWaveMeData]) -> None:
        """Create multiple devices."""
        for device in devices:
            if device.deviceType in ZWAVE_ME_PLATFORMS and self.platforms_inited:
                self.add_device(device)

    def on_device_update(self, new_info: ZWaveMeData) -> None:
        """Send signal to update device."""
        dispatcher_send(self._hass, f"ZWAVE_ME_INFO_{new_info.id}", new_info)

    def on_device_unavailable(self, device_id: str) -> None:
        """Send signal to set device unavailable."""
        dispatcher_send(self._hass, f"ZWAVE_ME_UNAVAILABLE_{device_id}")

    def on_device_destroy(self, device_id: str) -> None:
        """Send signal to destroy device."""
        dispatcher_send(self._hass, f"ZWAVE_ME_DESTROY_{device_id}")

    def remove_stale_devices(self, registry: dr.DeviceRegistry):
        """Remove old-format devices in the registry."""
        for device_id in self.device_ids:
            device = registry.async_get_device(
                identifiers={(DOMAIN, f"{self.config.unique_id}-{device_id}")}
            )
            if device is not None:
                registry.async_remove_device(device.id)


async def async_setup_platforms(
    hass: HomeAssistant, entry: ConfigEntry, controller: ZWaveMeController
) -> None:
    """Set up platforms."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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
            identifiers={(DOMAIN, self.device.deviceIdentifier)},
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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"ZWAVE_ME_UNAVAILABLE_{self.device.id}",
                self.set_unavailable_status,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"ZWAVE_ME_DESTROY_{self.device.id}", self.delete_entity
            )
        )

    @callback
    def get_new_data(self, new_data: ZWaveMeData) -> None:
        """Update info in the HAss."""
        self.device = new_data
        self._attr_available = not new_data.isFailed
        self.async_write_ha_state()

    @callback
    def set_unavailable_status(self):
        """Update status in the HAss."""
        self._attr_available = False
        self.async_write_ha_state()

    @callback
    def delete_entity(self) -> None:
        """Remove this entity."""
        self.hass.async_create_task(self.async_remove(force_remove=True))
