"""Button platform for the Yoto integration."""

from yoto_api import YotoError, YotoPlayer

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1

RESTART_BUTTON = ButtonEntityDescription(
    key="restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto button platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoRestartButton(coordinator, player)
        for player in coordinator.client.players.values()
    )


class YotoRestartButton(YotoEntity, ButtonEntity):
    """Button that restarts a Yoto player."""

    entity_description = RESTART_BUTTON

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, player)
        self._attr_unique_id = f"{player.id}_restart"

    async def async_press(self) -> None:
        """Restart the player."""
        try:
            await self.coordinator.client.restart(self._player_id)
        except YotoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
