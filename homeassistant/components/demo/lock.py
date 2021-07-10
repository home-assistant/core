"""Demo lock platform that has two fake locks."""
from homeassistant.components.lock import SUPPORT_OPEN, LockEntity
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo lock platform."""
    async_add_entities(
        [
            DemoLock("Front Door", STATE_LOCKED),
            DemoLock("Kitchen Door", STATE_UNLOCKED),
            DemoLock("Openable Lock", STATE_LOCKED, True),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoLock(LockEntity):
    """Representation of a Demo lock."""

    _attr_should_poll = False

    def __init__(self, name: str, state: str, openable: bool = False) -> None:
        """Initialize the lock."""
        self._attr_name = name
        self._attr_is_locked = state == STATE_LOCKED
        if openable:
            self._attr_supported_features = SUPPORT_OPEN

    def lock(self, **kwargs):
        """Lock the device."""
        self._attr_is_locked = True
        self.schedule_update_ha_state()

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._attr_is_locked = False
        self.schedule_update_ha_state()

    def open(self, **kwargs):
        """Open the door latch."""
        self._attr_is_locked = False
        self.schedule_update_ha_state()
