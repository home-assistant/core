"""Support for the Dynalite devices as entities."""
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, LOGGER


def async_setup_entry_base(
    hass, config_entry, async_add_entities, platform, entity_from_device
):
    """Record the async_add_entities function to add them later when received from Dynalite."""
    LOGGER.debug("Setting up %s entry = %s", platform, config_entry.data)
    bridge = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_entities_platform(devices):
        # assumes it is called with a single platform
        added_entities = []
        for device in devices:
            if device.category == platform:
                added_entities.append(entity_from_device(device, bridge))
        if added_entities:
            async_add_entities(added_entities)

    bridge.register_add_devices(platform, async_add_entities_platform)


class DynaliteBase:  # Deriving from Object so it doesn't override the entity (light, switch, cover, etc.)
    """Base class for the Dynalite entities."""

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

    @property
    def device_info(self):
        """Device info for this entity."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Dynalite",
        }

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
