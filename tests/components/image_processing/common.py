"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.image_processing import DOMAIN, ImageProcessingService
from homeassistant.const import ENTITY_MATCH_ALL, TargetKey
from homeassistant.core import HomeAssistant, callback


def scan(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Force process of all cameras or given entity."""
    hass.add_job(async_scan, hass, entity_id)


@callback
def async_scan(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Force process of all cameras or given entity."""
    data = {TargetKey.ENTITY_ID: entity_id} if entity_id else None
    hass.async_create_task(
        hass.services.async_call(DOMAIN, ImageProcessingService.SCAN, data)
    )
