"""Test the Fully Kiosk Browser image platform."""

from http import HTTPStatus
from unittest.mock import MagicMock

from fullykiosk import FullyKioskError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_image(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the image entity."""
    entity_image = "image.amazon_fire_screenshot"
    entity = hass.states.get(entity_image)
    assert entity
    assert entity.state == "unknown"
    entry = entity_registry.async_get(entity_image)
    assert entry
    assert entry.unique_id == "abcdef-123456-screenshot"

    mock_fully_kiosk.getScreenshot.return_value = b"image_bytes"
    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{entity_image}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Type"] == "image/png"
    assert await resp.read() == b"image_bytes"
    assert mock_fully_kiosk.getScreenshot.call_count == 1

    mock_fully_kiosk.getScreenshot.side_effect = FullyKioskError("error", "status")
    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{entity_image}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
