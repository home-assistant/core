"""Wake word constants."""

from typing import TYPE_CHECKING, Final

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.helpers.entity_component import EntityComponent

    from . import WakeWordDetectionEntity


DOMAIN: Final = "wake_word"
DATA_COMPONENT: HassKey[EntityComponent[WakeWordDetectionEntity]] = HassKey(DOMAIN)
