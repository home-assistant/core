"""Support for MyQ-Enabled lights."""
from pymyq.errors import MyQError

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyQEntity
from .const import DOMAIN, MYQ_COORDINATOR, MYQ_GATEWAY, MYQ_TO_HASS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myq lights."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    myq = data[MYQ_GATEWAY]
    coordinator = data[MYQ_COORDINATOR]

    async_add_entities(
        [MyQLight(coordinator, device) for device in myq.lamps.values()], True
    )


class MyQLight(MyQEntity, LightEntity):
    """Representation of a MyQ light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

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
