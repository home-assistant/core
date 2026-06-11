"""Select platform for the Yoto integration."""

from yoto_api import YotoPlayer

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1

HOUR_FORMATS = ["12", "24"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto select platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoHourFormatSelect(coordinator, player)
        for player in coordinator.client.players.values()
    )


class YotoHourFormatSelect(YotoEntity, SelectEntity):
    """Clock hour format setting of a Yoto player."""

    _attr_translation_key = "hour_format"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = HOUR_FORMATS

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, player)
        self._attr_unique_id = f"{player.id}_hour_format"

    @property
    def current_option(self) -> str | None:
        """Return the configured hour format."""
        hour_format = self.player.info.config.hour_format
        if hour_format is None:
            return None
        return str(hour_format)

    async def async_select_option(self, option: str) -> None:
        """Update the hour format."""
        await self._async_set_config(hour_format=int(option))
