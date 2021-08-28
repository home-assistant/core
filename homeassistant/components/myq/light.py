"""Support for MyQ-Enabled lights."""
import logging

from pymyq.errors import MyQError

from homeassistant.components.light import LightEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.exceptions import HomeAssistantError

from . import MyQEntity
from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY, MYQ_TO_HASS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up myq lights."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    async_add_entities(
        [MyQLight(coordinator, device) for device in myq.lamps.values()], True
    )


class MyQLight(MyQEntity, LightEntity):
    """Representation of a MyQ light."""

    _attr_supported_features = 0

    @property
    def is_on(self):
        """Return true if the light is on, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_ON

    @property
    def is_off(self):
        """Return true if the light is off, else False."""
        return MYQ_TO_HASS.get(self._device.state) == STATE_OFF

    async def async_turn_on(self, **kwargs):
        """Issue on command to light."""
        if self.is_on:
            return

        try:
            await self._device.turnon(wait_for_state=True)
        except MyQError as err:
            raise HomeAssistantError(
                f"Turning light {self._device.name} on failed with error: {err}"
            ) from err

        # Write new state to HASS
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Issue off command to light."""
        if self.is_off:
            return

        try:
            await self._device.turnoff(wait_for_state=True)
        except MyQError as err:
            raise HomeAssistantError(
                f"Turning light {self._device.name} off failed with error: {err}"
            ) from err

        # Write new state to HASS
        self.async_write_ha_state()
