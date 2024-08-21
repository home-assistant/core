"""The tests for the Ring button platform."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant,
    mock_ring_client,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.BUTTON)

    entry = entity_registry.async_get("button.ingress_open_door")
    assert entry.unique_id == "185036587-open_door"


async def test_button_opens_door(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
) -> None:
    """Tests the door open button works correctly."""
    await setup_platform(hass, Platform.BUTTON)

    mock_intercom = mock_ring_devices.get_device(185036587)
    mock_intercom.open_door.assert_not_called()

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.ingress_open_door"}, blocking=True
    )

    await hass.async_block_till_done(wait_background_tasks=True)
    mock_intercom.open_door.assert_called_once()
