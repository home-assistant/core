"""Platform for button integration for squeezebox."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SqueezeboxConfigEntry
from .const import SIGNAL_PLAYER_DISCOVERED
from .coordinator import SqueezeBoxPlayerUpdateCoordinator
from .entity import SqueezeboxEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

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
    *HARDWARE_MODELS_WITH_SCREEN,
    "Squeezebox Receiver",
]


@dataclass(frozen=True, kw_only=True)
class SqueezeboxButtonEntityDescription(ButtonEntityDescription):
    """Squeezebox Button description."""

    press_action: str


BUTTON_ENTITIES: tuple[SqueezeboxButtonEntityDescription, ...] = tuple(
    SqueezeboxButtonEntityDescription(
        key=f"preset_{i}",
        translation_key="preset",
        translation_placeholders={"index": str(i)},
        press_action=f"preset_{i}.single",
    )
    for i in range(1, 7)
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

        entities: list[SqueezeboxButtonEntity] = []

        entities.extend(
            SqueezeboxButtonEntity(player_coordinator, description)
            for description in BUTTON_ENTITIES
        )

        entities.extend(
            SqueezeboxButtonEntity(player_coordinator, description)
            for description in TONE_BUTTON_ENTITIES
            if player_coordinator.player.model in HARDWARE_MODELS_WITH_TONE
        )

        entities.extend(
            SqueezeboxButtonEntity(player_coordinator, description)
            for description in SCREEN_BUTTON_ENTITIES
            if player_coordinator.player.model in HARDWARE_MODELS_WITH_SCREEN
        )

        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PLAYER_DISCOVERED, _player_discovered)
    )


class SqueezeboxButtonEntity(SqueezeboxEntity, ButtonEntity):
    """Representation of Buttons for Squeezebox entities."""

    entity_description: SqueezeboxButtonEntityDescription

    def __init__(
        self,
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
        entity_description: SqueezeboxButtonEntityDescription,
    ) -> None:
        """Initialize the SqueezeBox Button."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{format_mac(self._player.player_id)}_{entity_description.key}"
        )

    async def async_press(self) -> None:
        """Execute the button action."""
        await self._player.async_query("button", self.entity_description.press_action)
