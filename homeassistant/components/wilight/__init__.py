"""The WiLight integration."""
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .parent_device import WiLightParent

# List the platforms that you want to support.
PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the WiLight with Config Flow component."""

    hass.data[DOMAIN] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a wilight config entry."""

    parent = WiLightParent(hass, entry)

    if not await parent.async_setup():
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = parent

    # Set up all platforms for this device/entry.
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload WiLight config entry."""

    # Unload entities for this entry/device.
    await asyncio.gather(
        *(
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in PLATFORMS
        )
    )

    # Cleanup
    parent = hass.data[DOMAIN][entry.entry_id]
    await parent.async_reset()
    del hass.data[DOMAIN][entry.entry_id]

    return True


class WiLightDevice(Entity):
    """Representation of a WiLight device.

    Contains the common logic for WiLight entities.
    """

    def __init__(self, api_device, index, item_name):
        """Initialize the device."""
        # WiLight specific attributes for every component type
        self._device_id = api_device.device_id
        self._sw_version = api_device.swversion
        self._client = api_device.client
        self._model = api_device.model
        self._name = item_name
        self._index = index
        self._unique_id = f"{self._device_id}_{self._index}"
        self._status = {}

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return a name for this WiLight item."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this WiLight item."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._unique_id)},
            "model": self._model,
            "manufacturer": "WiLight",
            "sw_version": self._sw_version,
            "via_device": (DOMAIN, self._device_id),
        }

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._client.is_connected)

    @callback
    def handle_event_callback(self, states):
        """Propagate changes through ha."""
        self._status = states
        self.async_write_ha_state()

    async def async_update(self):
        """Synchronize state with api_device."""
        await self._client.status(self._index)

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        await self._client.status(self._index)
