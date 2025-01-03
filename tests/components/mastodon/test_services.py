"""Tests for the Mastodon services."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.mastodon.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_CONTENT_WARNING,
    ATTR_STATUS,
    ATTR_VISIBILITY,
    DOMAIN,
)
from homeassistant.components.mastodon.services import SERVICE_POST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                ATTR_STATUS: "test toot",
            },
            {"status": "test toot", "spoiler_text": None, "visibility": None},
        ),
        (
            {ATTR_STATUS: "test toot", ATTR_VISIBILITY: "private"},
            {"status": "test toot", "spoiler_text": None, "visibility": "private"},
        ),
        (
            {
                ATTR_STATUS: "test toot",
                ATTR_CONTENT_WARNING: "Spoiler",
                ATTR_VISIBILITY: "private",
            },
            {"status": "test toot", "spoiler_text": "Spoiler", "visibility": "private"},
        ),
    ],
)
async def test_service_post(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    payload: dict[str, str],
    kwargs: dict[str, str | None],
) -> None:
    """Test the post service."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_POST,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
        }
        | payload,
        blocking=True,
        return_response=False,
    )

    mock_mastodon_client.status_post.assert_called_with(**kwargs)

    mock_mastodon_client.status_post.reset_mock()


async def test_service_entry_availability(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the services without valid entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    payload = {"status": "test toot"}

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id} | payload,
            blocking=True,
            return_response=False,
        )

    with pytest.raises(
        ServiceValidationError, match='Integration "mastodon" not found in registry'
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_POST,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=False,
        )
