"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.scene import DOMAIN, SceneService
from homeassistant.const import ENTITY_MATCH_ALL, TargetKey
from homeassistant.core import HomeAssistant


def activate(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Activate a scene."""
    data = {}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SceneService.TURN_ON, data)
