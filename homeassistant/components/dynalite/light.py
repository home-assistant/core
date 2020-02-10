"""Support for Dynalite channels as lights."""
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light
from homeassistant.core import callback

from .const import DOMAIN, LOGGER


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""
    LOGGER.debug("async_setup_entry light entry = %s", config_entry.data)
    bridge = hass.data[DOMAIN][config_entry.entry_id]
    bridge.register_add_entities(async_add_entities)


class DynaliteLight(Light):
    """Representation of a Dynalite Channel as a Home Assistant Light."""

    def __init__(self, device, bridge):
        """Initialize the base class."""
        self._device = device
        self._bridge = bridge

    @property
    def device(self):
        """Return the underlying device - mostly for testing."""
        return self._device

    @property
    def name(self):
        """Return the name of the entity."""
        return self._device.name

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._device.unique_id

    @property
    def available(self):
        """Return if entity is available."""
        return self._device.available

    @property
    def hidden(self):
        """Return true if this entity should be hidden from UI."""
        return self._device.hidden

    async def async_update(self):
        """Update the entity."""
        return

    @property
    def device_info(self):
        """Device info for this entity."""
        return self._device.device_info

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._device.brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        await self._device.async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._device.async_turn_off(**kwargs)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @callback
    def try_schedule_ha(self):
        """Schedule update HA state if configured."""
        if self.hass:
            self.schedule_update_ha_state()
