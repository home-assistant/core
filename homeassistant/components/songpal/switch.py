"""Switch platform for Songpal."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SongpalCoordinator
from .entity import SongpalSettingEntity
from .media_player import MEDIA_PLAYER_SETTINGS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up songpal select entities."""
    coordinator: SongpalCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    for setting in coordinator.settings_definitions:
        _LOGGER.debug("Looking at setting %r", setting)

        # Ignore settings that are exposed via MediaPlayerEntity.
        if setting.titleTextID in MEDIA_PLAYER_SETTINGS:
            continue

        if setting.type == "booleanTarget":
            entities.append(SongpalSwitchEntity(coordinator, setting))

    async_add_entities(entities)


class SongpalSwitchEntity(SwitchEntity, SongpalSettingEntity):
    """Base entity for Songpal boolean settings."""

    @property
    def is_on(self) -> bool:
        """Convert the setting value to a switch state."""
        return self._current_value == "on"

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the setting on."""
        await self.update_setting("on")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the setting off."""
        await self.update_setting("off")
