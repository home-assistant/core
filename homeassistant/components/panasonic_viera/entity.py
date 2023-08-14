"""Base entity for Panasonic Viera."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.trigger import PluggableAction

from . import Remote
from .triggers.turn_on import async_get_turn_on_trigger


class PanasonicVieraEntity(Entity):
    """Base entity for Panasonic Viera."""

    def __init__(self, remote: Remote) -> None:
        """Initialize base entity."""
        self._remote = remote
        self._turn_on = PluggableAction(self.async_write_ha_state)

    async def async_added_to_hass(self) -> None:
        """Connect and subscribe to dispatcher signals and state updates."""
        await super().async_added_to_hass()

        if (entry := self.registry_entry) and entry.device_id:
            self.async_on_remove(
                self._turn_on.async_register(
                    self.hass, async_get_turn_on_trigger(entry.device_id)
                )
            )
