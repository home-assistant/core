"""Button for force sync the schedules."""

from powerplanner import PowerplannerHub

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .binary_sensor import UpdateCoordinator
from .const import DOMAIN
from .entity import PowerPlannerEntityBase


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up powerplanner control buttons."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = UpdateCoordinator(hass, hub, config_entry)
    async_add_entities([PowerplannerSyncButton(config_entry, coordinator, hub)])


class PowerplannerSyncButton(PowerPlannerEntityBase, ButtonEntity):
    """The sync button entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: UpdateCoordinator,
        hub: PowerplannerHub,
    ) -> None:
        """Init syncbutton."""
        PowerPlannerEntityBase.__init__(self, hash(hub.api_key))
        self._attr_name = "Sync powerplanner"
        self._attr_unique_id = f"sync-button_{config_entry.entry_id}"
        self.config_entry = (config_entry,)
        self.coordinator = coordinator

    async def async_press(self) -> None:
        """Triggers the coordinator update."""
        await self.coordinator.async_refresh()
