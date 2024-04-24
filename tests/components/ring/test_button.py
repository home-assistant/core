"""The tests for the Ring button platform."""

import requests_mock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_entity_registry(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.BUTTON)

    entry = entity_registry.async_get("button.ingress_open_door")
    assert entry.unique_id == "185036587-open_door"


async def test_button_opens_door(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Tests the door open button works correctly."""
    await setup_platform(hass, Platform.BUTTON)

    # Mocks the response for opening door
    mock = requests_mock.put(
        "https://api.ring.com/commands/v1/devices/185036587/device_rpc",
        status_code=200,
        text="{}",
    )

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.ingress_open_door"}, blocking=True
    )

    await hass.async_block_till_done()
    assert mock.call_count == 1
