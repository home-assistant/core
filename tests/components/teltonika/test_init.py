"""Test the Teltonika integration."""

from unittest.mock import MagicMock

from aiohttp import ClientResponseError, ContentTypeError
import pytest
from syrupy.assertion import SnapshotAssertion
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            TeltonikaConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            ContentTypeError(
                request_info=MagicMock(),
                history=(),
                status=403,
                message="Attempt to decode JSON with unexpected mimetype: text/html",
                headers={},
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=401,
                message="Unauthorized",
                headers={},
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=403,
                message="Forbidden",
                headers={},
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            TeltonikaAuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
    ids=[
        "connection_error",
        "content_type_403",
        "response_401",
        "response_403",
        "auth_error",
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test various setup errors result in appropriate config entry states."""
    mock_teltasync.return_value.get_device_info.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_device_registry_creation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device registry creation."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "1234567890")})
    assert device is not None
    assert device == snapshot
