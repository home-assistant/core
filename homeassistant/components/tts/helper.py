"""Provide helper functions for the TTS."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from .const import DATA_TTS_MANAGER, DOMAIN

if TYPE_CHECKING:
    from . import SpeechManager, TextToSpeechEntity
    from .legacy import Provider


def get_engine_instance(
    hass: HomeAssistant, engine: str
) -> TextToSpeechEntity | Provider | None:
    """Get engine instance."""
    component: EntityComponent[TextToSpeechEntity] = hass.data[DOMAIN]

    if entity := component.get_entity(engine):
        return entity

    manager: SpeechManager = hass.data[DATA_TTS_MANAGER]
    return manager.providers.get(engine)
