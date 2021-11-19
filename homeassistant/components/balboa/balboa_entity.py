"""Base class for Balboa Spa Client integration."""
import time

from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import _LOGGER, DOMAIN


class BalboaEntity(Entity):
    """Abstract class for all Balboa platforms.

    Once you connect to the spa's port, it continuously sends data (at a rate
    of about 5 per second!).  The API updates the internal states of things
    from this stream, and all we have to do is read the values out of the
    accessors.
    """

    _attr_should_poll = False

    def __init__(self, hass, entry, client, devtype, num=None):
        """Initialize the spa entity."""
        self._client = client
        self._device_name = self._client.get_model_name()
        self._type = devtype
        self._num = num
        self._attr_unique_id = f'{self._device_name}-{self._type}{self._num or ""}-{self._client.get_macaddr().replace(":","")[-6:]}'
        self._attr_name = f'{self._device_name}: {self._type}{self._num or ""}'
        self._attr_device_info = DeviceInfo(
            name=self._device_name,
            manufacturer="Balboa Water Group",
            model=self._client.get_model_name(),
            sw_version=self._client.get_ssid(),
            connections={(CONNECTION_NETWORK_MAC, self._client.get_macaddr())},
        )

        # map the blower and heatmodes back and forth
        self.balboa_to_ha_blower_map = {
            self._client.BLOWER_OFF: FAN_OFF,
            self._client.BLOWER_LOW: FAN_LOW,
            self._client.BLOWER_MEDIUM: FAN_MEDIUM,
            self._client.BLOWER_HIGH: FAN_HIGH,
        }
        self.ha_to_balboa_blower_map = {
            value: key for key, value in self.balboa_to_ha_blower_map.items()
        }

        self.balboa_to_ha_heatmode_map = {
            self._client.HEATMODE_READY: HVAC_MODE_HEAT,
            self._client.HEATMODE_RNR: HVAC_MODE_AUTO,
            self._client.HEATMODE_REST: HVAC_MODE_OFF,
        }

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self._update_callback)
        )

    @callback
    def _update_callback(self) -> None:
        """Call from dispatcher when state changes."""
        _LOGGER.debug("Updating %s state with new data", self.name)
        self.async_write_ha_state()

    @property
    def assumed_state(self) -> bool:
        """Return whether the state is based on actual reading from device."""
        if (self._client.lastupd + 5 * 60) < time.monotonic():
            return True
        return False

    @property
    def available(self) -> bool:
        """Return whether the entity is available or not."""
        return self._client.connected
