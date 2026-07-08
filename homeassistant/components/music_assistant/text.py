"""Music Assistant text platform."""

from typing import Final, override

from music_assistant_client.client import MusicAssistantClient
from music_assistant_models.enums import EventType
from music_assistant_models.event import MassEvent
from music_assistant_models.player import PlayerOption, PlayerOptionType

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MusicAssistantConfigEntry
from .const import LOGGER
from .entity import MusicAssistantPlayerOptionEntity
from .helpers import catch_musicassistant_error, get_party_device_info

PLAYER_OPTIONS_TEXT: Final[dict[str, bool]] = {
    # translation_key: enabled_by_default
    "network_name": True
}

PARTY_MODE_TEXTS = {
    "party_name": ("mdi:rename-box", None),
    "qr_text": ("mdi:text-box", EntityCategory.CONFIG),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant text Entities (Player Options) from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        player = mass.players.get(player_id)
        if player is None:
            return
        entities: list[MusicAssistantPlayerConfigText] = []
        for player_option in player.options:
            if (
                not player_option.read_only
                and player_option.type == PlayerOptionType.STRING
                and not player_option.options  # these we map to select
            ):
                # we ignore entities with unknown translation keys.
                if player_option.translation_key not in PLAYER_OPTIONS_TEXT:
                    continue

                entities.append(
                    MusicAssistantPlayerConfigText(
                        mass,
                        player_id,
                        player_option=player_option,
                        entity_description=TextEntityDescription(
                            key=player_option.key,
                            translation_key=player_option.translation_key,
                            entity_registry_enabled_default=PLAYER_OPTIONS_TEXT[
                                player_option.translation_key
                            ],
                        ),
                    )
                )
        async_add_entities(entities)

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.TEXT, add_player)

    def add_party_mode(instance_id: str) -> None:
        """Handle add party mode."""

        async def _add_entities() -> None:
            entities: list[MusicAssistantPartyModeText] = []
            if party_config := await mass.config.get_provider_config(instance_id):
                for text_key, (icon, category) in PARTY_MODE_TEXTS.items():
                    if text_key not in party_config.values:
                        continue

                    entities.append(
                        MusicAssistantPartyModeText(
                            mass,
                            instance_id,
                            config_key=text_key,
                            entity_description=TextEntityDescription(
                                key=f"party_mode_{text_key}",
                                translation_key=f"party_mode_{text_key}",
                                icon=icon,
                                entity_category=category,
                            ),
                        )
                    )
            async_add_entities(entities)

        entry.async_create_background_task(
            hass, _add_entities(), "music_assistant_party_mode_texts"
        )

    entry.runtime_data.party_handlers.setdefault(Platform.TEXT, add_party_mode)


class MusicAssistantPlayerConfigText(MusicAssistantPlayerOptionEntity, TextEntity):
    """Representation of a text entity to control player provider dependent settings."""

    def __init__(
        self,
        mass: MusicAssistantClient,
        player_id: str,
        player_option: PlayerOption,
        entity_description: TextEntityDescription,
    ) -> None:
        """Initialize MusicAssistantPlayerConfigtext."""
        super().__init__(mass, player_id, player_option)

        self.entity_description = entity_description

    @catch_musicassistant_error
    @override
    async def async_set_value(self, value: str) -> None:
        """Set text value."""
        await self.mass.players.set_option(self.player_id, self.mass_option_key, value)

    @override
    def on_player_option_update(self, player_option: PlayerOption) -> None:
        """Update on player option update."""
        self._attr_native_value = (
            player_option.value if isinstance(player_option.value, str) else None
        )


class MusicAssistantPartyModeText(TextEntity):
    """Representation of a Text entity to control party mode settings."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        mass: MusicAssistantClient,
        instance_id: str,
        config_key: str,
        entity_description: TextEntityDescription,
    ) -> None:
        """Initialize."""
        self.mass = mass
        self.instance_id = instance_id
        self.config_key = config_key
        self.entity_description = entity_description
        self._attr_device_info = get_party_device_info(instance_id)
        self._attr_unique_id = f"{instance_id}_{config_key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await self.async_on_update()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_mass_update,
                EventType.PROVIDERS_UPDATED,
            )
        )

    async def __on_mass_update(self, event: MassEvent) -> None:
        """Call when we receive an event from MusicAssistant."""
        await self.async_on_update()
        self.async_write_ha_state()

    async def async_on_update(self) -> None:
        """Update text state."""
        try:
            party_config = await self.mass.config.get_provider_config(self.instance_id)
            if value := party_config.get_value(self.config_key):
                self._attr_native_value = str(value)
            else:
                self._attr_native_value = ""
            self._attr_available = True
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("Error in text update: %s", err)
            self._attr_available = False

    @catch_musicassistant_error
    @override
    async def async_set_value(self, value: str) -> None:
        """Set a new value."""
        LOGGER.debug(
            "Setting text %s to %s for %s", self.config_key, value, self.instance_id
        )
        await self.mass.config.save_provider_config(
            provider_domain="party",
            instance_id=self.instance_id,
            values={self.config_key: value},
        )
