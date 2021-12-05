"""Base class for Balboa Spa Client integration."""
import time

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import SIGNAL_UPDATE


class BalboaEntity(Entity):
    """Abstract class for all Balboa platforms.

    Once you connect to the spa's port, it continuously sends data (at a rate
    of about 5 per second!).  The API updates the internal states of things
    from this stream, and all we have to do is read the values out of the
    accessors.
    """

    _attr_should_poll = False

    def __init__(self, entry, client, devtype, num=None):
        """Initialize the spa entity."""
        self._client = client
        self._device_name = self._client.get_model_name()
        self._type = devtype
        self._num = num
        self._entry = entry
        self._attr_unique_id = f'{self._device_name}-{self._type}{self._num or ""}-{self._client.get_macaddr().replace(":","")[-6:]}'
        self._attr_name = f'{self._device_name}: {self._type}{self._num or ""}'
        self._attr_device_info = DeviceInfo(
            name=self._device_name,
            manufacturer="Balboa Water Group",
            model=self._client.get_model_name(),
            sw_version=self._client.get_ssid(),
            connections={(CONNECTION_NETWORK_MAC, self._client.get_macaddr())},
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE.format(self._entry.entry_id),
                self.async_write_ha_state,
            )
        )

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        return (self._client.lastupd + 5 * 60) < time.time()

    @property
    def available(self) -> bool:
        """Return whether the entity is available or not."""
        return self._client.connected
