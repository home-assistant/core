"""Tests for the Mastodon services."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mastodon.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_STATUS,
    DOMAIN,
)
from homeassistant.components.mastodon.services import SERVICE_POST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_service_post(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the post service."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_POST,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_STATUS: "test toot",
        },
        blocking=True,
        return_response=False,
    )

    assert mock_mastodon_client.status_post.assert_called_once
