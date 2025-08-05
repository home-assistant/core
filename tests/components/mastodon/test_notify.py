"""Tests for the Mastodon notify platform."""

from unittest.mock import AsyncMock

from mastodon.Mastodon import MastodonAPIError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    assert hass.services.has_service(NOTIFY_DOMAIN, "trwnh_mastodon_social")

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        "trwnh_mastodon_social",
        {
            "message": "test toot",
        },
        blocking=True,
        return_response=False,
    )

    assert mock_mastodon_client.status_post.assert_called_once


async def test_notify_failed(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the notify raising an error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_mastodon_client.status_post.side_effect = MastodonAPIError

    with pytest.raises(HomeAssistantError, match="Unable to send message"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            "trwnh_mastodon_social",
            {
                "message": "test toot",
            },
            blocking=True,
            return_response=False,
        )
