"""Button platform for the Tewke integration.

Exposes a restart (reboot) button for the Tewke Tap Panel.
"""

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import TewkeEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TewkeCoordinator
    from .data import TewkeConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tewke button entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([TewkeRestartButton(coordinator=coordinator)])


class TewkeRestartButton(TewkeEntity, ButtonEntity):
    """Button entity to restart the Tewke Tap Panel."""

    _attr_name = "Restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TewkeCoordinator) -> None:
        """Initialise the restart button entity."""
        super().__init__(coordinator)
        hardware_id = coordinator.data["config"].hardware_id
        self._attr_unique_id = f"{hardware_id}_restart"

    async def async_press(self) -> None:
        """Send a restart command to the Tap Panel."""
        tap = self.coordinator.config_entry.runtime_data.tap
        await tap.restart()
