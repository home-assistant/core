"""Test trigger template entity."""

from homeassistant.components.template import trigger_entity
from homeassistant.components.template.coordinator import TriggerUpdateCoordinator
from homeassistant.core import HomeAssistant


async def test_reference_blueprints_is_none(hass: HomeAssistant) -> None:
    """Test template entity requires hass to be set before accepting templates."""
    coordinator = TriggerUpdateCoordinator(hass, {})
    entity = trigger_entity.TriggerEntity(hass, coordinator, {})

    assert entity.referenced_blueprint is None
