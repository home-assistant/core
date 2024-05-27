"""Test Blue Current Init Component."""

from datetime import timedelta
from unittest.mock import patch

from bluecurrent_api.exceptions import (
    BlueCurrentException,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)
import pytest

from homeassistant.components.blue_current import async_setup_entry
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    IntegrationError,
)

from . import init_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test load and unload entry."""
    with (
        patch("homeassistant.components.blue_current.Client.validate_api_token"),
        patch("homeassistant.components.blue_current.Client.wait_for_charge_points"),
        patch("homeassistant.components.blue_current.Client.disconnect"),
        patch(
            "homeassistant.components.blue_current.Client.connect",
            lambda self, on_data, on_open: hass.loop.create_future(),
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("api_error", "config_error"),
    [
        (InvalidApiToken, ConfigEntryAuthFailed),
        (BlueCurrentException, ConfigEntryNotReady),
    ],
)
async def test_config_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_error: BlueCurrentException,
    config_error: IntegrationError,
) -> None:
    """Test if the correct config error is raised when connecting to the api fails."""
    with (
        patch(
            "homeassistant.components.blue_current.Client.validate_api_token",
            side_effect=api_error,
        ),
        pytest.raises(config_error),
    ):
        config_entry.add_to_hass(hass)
        await async_setup_entry(hass, config_entry)


async def test_connect_websocket_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconnect when connect throws a WebsocketError."""

    with patch("homeassistant.components.blue_current.DELAY", 0):
        mock_client, started_loop, future_container = await init_integration(
            hass, config_entry
        )
        future_container.future.set_exception(WebsocketError)

        await started_loop.wait()
        assert mock_client.connect.call_count == 2


async def test_connect_request_limit_reached_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconnect when connect throws a RequestLimitReached."""

    mock_client, started_loop, future_container = await init_integration(
        hass, config_entry
    )
    future_container.future.set_exception(RequestLimitReached)
    mock_client.get_next_reset_delta.return_value = timedelta(seconds=0)

    await started_loop.wait()
    assert mock_client.get_next_reset_delta.call_count == 1
    assert mock_client.connect.call_count == 2
