"""Tests for the Amazon Polly integration setup."""

from unittest.mock import AsyncMock, MagicMock

from botocore.exceptions import ClientError, EndpointConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_polly_client: AsyncMock,
) -> None:
    """Test the entry sets up and closes the client on unload."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_polly_client.__aexit__.assert_awaited_once()

    # The shutdown listener is removed on unload, so the client isn't closed twice.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    mock_polly_client.__aexit__.assert_awaited_once()


async def test_client_closed_on_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_polly_client: AsyncMock,
) -> None:
    """Test the client is closed when Home Assistant shuts down."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_polly_client.__aexit__.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    mock_polly_client.__aexit__.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "state", "reauth"),
    [
        pytest.param(
            ClientError(
                {"Error": {"Code": "InvalidSignatureException", "Message": "Bad"}},
                "DescribeVoices",
            ),
            ConfigEntryState.SETUP_ERROR,
            True,
            id="invalid_auth",
        ),
        pytest.param(
            EndpointConnectionError(endpoint_url="https://polly.amazonaws.com"),
            ConfigEntryState.SETUP_RETRY,
            False,
            id="cannot_connect",
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    mock_polly_client: AsyncMock,
    side_effect: Exception,
    state: ConfigEntryState,
    reauth: bool,
) -> None:
    """Test rejected credentials start reauth and outages retry."""
    mock_polly_client.describe_voices.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"})) is reauth
    mock_session.return_value.create_client.return_value.__aexit__.assert_awaited_once()
