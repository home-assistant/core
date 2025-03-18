"""Platform for button integration for squeezebox."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SqueezeboxConfigEntry
from .const import SIGNAL_PLAYER_DISCOVERED
from .coordinator import SqueezeBoxPlayerUpdateCoordinator
from .entity import SqueezeboxEntity

_LOGGER = logging.getLogger(__name__)

HARDWARE_MODELS_WITH_SCREEN = [
    "Squeezebox Boom",
    "Squeezebox Radio",
    "Transporter",
    "Squeezebox Touch",
    "Squeezebox",
    "SliMP3",
    "Squeezebox 1",
    "Squeezebox 2",
    "Squeezebox 3",
]

HARDWARE_MODELS_WITH_TONE = [
    "Squeezebox Boom",
    "Squeezebox Radio",
    "Transporter",
    "Squeezebox Touch",
    "Squeezebox",
    "SliMP3",
    "Squeezebox 1",
    "Squeezebox 2",
    "Squeezebox 3",
    "Squeezebox Receiver",
]


@dataclass(frozen=True, kw_only=True)
class SqueezeboxButtonEntityDescription(ButtonEntityDescription):
    """Squeezebox Button description."""

    press_action: str


#    models: list[str] = field(default_factory=list)


BUTTON_ENTITIES: tuple[SqueezeboxButtonEntityDescription, ...] = (
    SqueezeboxButtonEntityDescription(
        key="preset_1",
        translation_key="preset_1",
        press_action="preset_1.single",
    ),
    SqueezeboxButtonEntityDescription(
        key="preset_2",
        translation_key="preset_2",
        press_action="preset_2.single",
    ),
    SqueezeboxButtonEntityDescription(
        key="preset_3",
        translation_key="preset_3",
        press_action="preset_3.single",
    ),
    SqueezeboxButtonEntityDescription(
        key="preset_4",
        translation_key="preset_4",
        press_action="preset_4.single",
    ),
    SqueezeboxButtonEntityDescription(
        key="preset_5",
        translation_key="preset_5",
        press_action="preset_5.single",
    ),
    SqueezeboxButtonEntityDescription(
        key="preset_6",
        translation_key="preset_6",
        press_action="preset_6.single",
    ),
)

SCREEN_BUTTON_ENTITIES: tuple[SqueezeboxButtonEntityDescription, ...] = (
    SqueezeboxButtonEntityDescription(
        key="brightness_up",
        translation_key="brightness_up",
        press_action="brightness_up",
    ),
    SqueezeboxButtonEntityDescription(
        key="brightness_down",
        translation_key="brightness_down",
        press_action="brightness_down",
    ),
)

TONE_BUTTON_ENTITIES: tuple[SqueezeboxButtonEntityDescription, ...] = (
    SqueezeboxButtonEntityDescription(
        key="bass_up",
        translation_key="bass_up",
        press_action="bass_up",
    ),
    SqueezeboxButtonEntityDescription(
        key="bass_down",
        translation_key="bass_down",
        press_action="bass_down",
    ),
    SqueezeboxButtonEntityDescription(
        key="treble_up",
        translation_key="treble_up",
        press_action="treble_up",
    ),
    SqueezeboxButtonEntityDescription(
        key="treble_down",
        translation_key="treble_down",
        press_action="treble_down",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Squeezebox button platform from a server config entry."""

    # Add button entities when player discovered
    async def _player_discovered(
        player_coordinator: SqueezeBoxPlayerUpdateCoordinator,
    ) -> None:
        _LOGGER.debug(
            "Setting up button entity for player %s, model %s",
            player_coordinator.player.name,
            player_coordinator.player.model,
        )

        async_add_entities(
            SqueezeboxButtonEntity(player_coordinator, description)
            for description in BUTTON_ENTITIES
        )

        async_add_entities(
            SqueezeboxButtonEntity(player_coordinator, description)
            for description in TONE_BUTTON_ENTITIES
            if player_coordinator.player.model in HARDWARE_MODELS_WITH_TONE
        )

        async_add_entities(
            SqueezeboxButtonEntity(player_coordinator, description)
            for description in SCREEN_BUTTON_ENTITIES
            if player_coordinator.player.model in HARDWARE_MODELS_WITH_SCREEN
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PLAYER_DISCOVERED, _player_discovered)
    )


class SqueezeboxButtonEntity(
    SqueezeboxEntity, ButtonEntity
):
    """Representation of Buttons for Squeezebox entities."""

    def __init__(
        self,
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
        entity_description: SqueezeboxButtonEntityDescription,
    ) -> None:
        """Initialize the SqueezeBox Button."""
        super().__init__(coordinator)
        SqueezeboxEntity.__init__(self, coordinator)
        self.entity_description: SqueezeboxButtonEntityDescription = entity_description
        self._attr_unique_id = f"{self._player.name}_{self.entity_description.key}"

    async def async_press(self) -> None:
        """Execute the button action."""
        all_params = ["button"]
        all_params.extend([self.entity_description.press_action])
        await self._player.async_query(*all_params)
