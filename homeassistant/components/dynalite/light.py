"""Support for Dynalite channels as lights."""
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, LOGGER


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""
    LOGGER.debug("Setting up light entry = %s", config_entry.data)
    bridge = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_lights(devices):
        added_lights = []
        for device in devices:
            if device.category == "light":
                added_lights.append(DynaliteLight(device, bridge))
        if added_lights:
            async_add_entities(added_lights)

    bridge.register_add_devices(async_add_lights)


class DynaliteLight(Light):
    """Representation of a Dynalite Channel as a Home Assistant Light."""

    def __init__(self, device, bridge):
        """Initialize the base class."""
        self._device = device
        self._bridge = bridge

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

    async def async_update(self):
        """Update the entity."""
        return

    @property
    def device_info(self):
        """Device info for this entity."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Dynalite",
        }

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

    async def async_added_to_hass(self):
        """Added to hass so need to register to dispatch."""
        # register for device specific update
        async_dispatcher_connect(
            self.hass,
            self._bridge.update_signal(self._device),
            self.async_schedule_update_ha_state,
        )
        # register for wide update
        async_dispatcher_connect(
            self.hass, self._bridge.update_signal(), self.async_schedule_update_ha_state
        )
