"""Tests for the Mastodon notify platform."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_notify(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sending a message."""
    await setup_integration(hass, mock_config_entry)

    assert hass.services.has_service(NOTIFY_DOMAIN, "mastodon")

    response = await hass.services.async_call(
        NOTIFY_DOMAIN,
        "mastodon",
        {
            "message": "test toot",
        },
        blocking=True,
    )
    assert response is None
