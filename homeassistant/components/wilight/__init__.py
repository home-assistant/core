"""The WiLight integration."""

from typing import Any

from pywilight.wilight_device import PyWiLightDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .parent_device import WiLightParent

DOMAIN = "wilight"

# List the platforms that you want to support.
PLATFORMS = [Platform.COVER, Platform.FAN, Platform.LIGHT, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a wilight config entry."""

    parent = WiLightParent(hass, entry)

    if not await parent.async_setup():
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = parent

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload WiLight config entry."""

    # Unload entities for this entry/device.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup
    parent = hass.data[DOMAIN][entry.entry_id]
    await parent.async_reset()
    del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


class WiLightDevice(Entity):
    """Representation of a WiLight device.

    Contains the common logic for WiLight entities.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, api_device: PyWiLightDevice, index: str, item_name: str) -> None:
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._device_id = api_device.device_id
        self._client = api_device.client
        self._index = index
        self._status: dict[str, Any] = {}

        self._attr_unique_id = f"{self._device_id}_{index}"
        self._attr_device_info = DeviceInfo(
            name=item_name,
            identifiers={(DOMAIN, self._attr_unique_id)},
            model=api_device.model,
            manufacturer="WiLight",
            sw_version=api_device.swversion,
            via_device=(DOMAIN, self._device_id),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def handle_event_callback(self, states: dict[str, Any]) -> None:
        """Propagate changes through ha."""
        self._status = states
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Synchronize state with api_device."""
        await self._client.status(self._index)

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        await self._client.status(self._index)
