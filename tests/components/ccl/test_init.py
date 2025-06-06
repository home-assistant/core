"""Test initialization of ccl."""

from http import HTTPStatus
import logging
from urllib.parse import urlparse

import pytest

from homeassistant.components.webhook import async_generate_url
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import WEBHOOK_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

_LOGGER = logging.getLogger(__name__)


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    (
        "headers",
        "expected_code",
    ),
    [
        (
            {"Content-Type": "application/json"},
            HTTPStatus.OK,
        ),  # Success
        (
            None,
            HTTPStatus.OK,
        ),  # Missing Headers
        (
            {"Content-Type": "text/html"},
            HTTPStatus.BAD_REQUEST,
        ),  # False Content-Type
    ],
)
async def test_webhook_post(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    headers: dict[str, str],
    expected_code: HTTPStatus,
) -> None:
    """Test webhook callback."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)
    body = {"Hello": "World"}
    resp = await client.post(urlparse(webhook_url).path, headers=headers, json=body)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    assert resp.status == expected_code
