"""Base class for Balboa Spa Client integration."""
import time

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import _LOGGER, DOMAIN, SPA


class BalboaEntity(Entity):
    """Abstract class for all Balboa platforms.

    Once you connect to the spa's port, it continuously sends data (at a rate
    of about 5 per second!).  The API updates the internal states of things
    from this stream, and all we have to do is read the values out of the
    accessors.
    """

    _attr_should_poll = False

    def __init__(self, hass, entry, devtype, num=None):
        """Initialize the spa entity."""
        self.hass = hass
        self._client = hass.data[DOMAIN][entry.entry_id][SPA]
        self._device_name = entry.data[CONF_NAME]
        self._type = devtype
        self._num = num
        self._attr_unique_id = f'{self._device_name}-{self._type}{self._num or ""}-{self._client.get_macaddr().replace(":","")[-6:]}'
        self._attr_name = f'{self._device_name}: {self._type}{self._num or ""}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._client.get_macaddr())},
            name=self._device_name,
            manufacturer="Balboa Water Group",
            model=self._client.get_model_name(),
            sw_version=self._client.get_ssid(),
            connections={(CONNECTION_NETWORK_MAC, self._client.get_macaddr())},
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Call from dispatcher when state changes."""
        _LOGGER.debug("Updating %s state with new data", self.name)
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if (self._client.lastupd + 5 * 60) < time.time():
            return True
        return False

    @property
    def available(self) -> bool:
        """Return whether the entity is available or not."""
        return self._client.connected
