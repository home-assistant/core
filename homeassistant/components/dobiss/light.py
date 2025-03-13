"""Support for dobiss lights."""
import logging

from dobissapi import DobissAnalogOutput, DobissLight, DobissOutput

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    LightEntity,
    ColorMode, 
)
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_IGNORE_ZIGBEE_DEVICES, DOMAIN, KEY_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up dobisslights."""

    _LOGGER.debug(f"Setting up light component of {DOMAIN}")

    dobiss = hass.data[DOMAIN][config_entry.entry_id][KEY_API].api

    light_entities = dobiss.get_devices_by_type(DobissLight)
    entities = []
    for d in light_entities:
        entities.append(HADobissLight(d))
    if entities:
        async_add_entities(entities)


class HADobissLight(LightEntity):
    """Dobiss light device."""

    should_poll = False

    def __init__(self, dobisslight: DobissOutput):
        """Init dobiss light device."""
        super().__init__()
        self._dobisslight = dobisslight
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if self._dobisslight.dimmable:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, f"address_{self._dobisslight.address}")},
            "name": f"Dobiss Device {self._dobisslight.address}",
            "manufacturer": "dobiss",
        }

    @property
    def extra_state_attributes(self):
        """Return supported attributes."""
        return self._dobisslight.attributes

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._dobisslight.register_callback(self.async_write_ha_state)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.signal_handler)
        )

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._dobisslight.remove_callback(self.async_write_ha_state)

    async def signal_handler(self, data):
        """Handle domain-specific signal by calling appropriate method."""
        entity_ids = data[ATTR_ENTITY_ID]

        if entity_ids == ENTITY_MATCH_NONE:
            return

        if entity_ids == ENTITY_MATCH_ALL or self.entity_id in entity_ids:
            params = {
                key: value
                for key, value in data.items()
                if key not in ["entity_id", "method"]
            }
            await getattr(self, data["method"])(**params)

    async def turn_on_service(
        self, brightness=None, delayon=None, delayoff=None, from_pir=False
    ):
        await self._dobisslight.turn_on(
            brightness=brightness, delayon=delayon, delayoff=delayoff, from_pir=from_pir
        )

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if not self._dobisslight.dimmable:
            return None
        # dobiss works from 0-100, ha from 0-255
        return (self._dobisslight.value / 100) * 255

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._dobisslight.is_on

    async def async_turn_on(self, **kwargs):
        """Turn on or control the light."""
        # dobiss works from 0-100, ha from 0-255
        brightness = 100
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((kwargs.get(ATTR_BRIGHTNESS) / 255) * 100)
        await self._dobisslight.turn_on(brightness)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._dobisslight.turn_off()

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if isinstance(self._dobisslight, DobissAnalogOutput):
            return "mdi:hvac"
        return super().icon

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        if self._dobisslight.dimmable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self):
        """Return the supported color modes."""
        return self._attr_supported_color_modes

    @property
    def name(self):
        """Return the display name of this light."""
        return self._dobisslight.name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._dobisslight.object_id
