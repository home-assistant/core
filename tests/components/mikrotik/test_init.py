"""Test Mikrotik setup process."""

import inspect
from unittest.mock import MagicMock, patch

from librouteros.exceptions import ConnectionClosed, LibRouterosError
import pytest

from homeassistant.components import mikrotik
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with (
        patch("librouteros.create_transport"),
        patch("librouteros.Api.readResponse") as mock_api,
    ):
        yield mock_api


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


async def test_hub_connection_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test setup fails due to connection error."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_authentication_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test setup fails due to authentication error."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = LibRouterosError("invalid user name or password")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


def test_login_method_with_fallback_uses_token_for_legacy_auth() -> None:
    """Test legacy fallback uses token auth after plain auth rejection."""
    api = MagicMock()

    with (
        patch(
            "homeassistant.components.mikrotik.coordinator.login_plain",
            side_effect=mikrotik.coordinator.librouteros.exceptions.FatalError(
                "cannot log in"
            ),
        ) as mock_plain,
        patch("homeassistant.components.mikrotik.coordinator.login_token") as mock_token,
    ):
        mikrotik.coordinator._login_method_with_fallback(api, "user", "pass")

    mock_plain.assert_called_once_with(api, "user", "pass")
    mock_token.assert_called_once_with(api, "user", "pass")


def test_get_api_uses_login_method_kwarg_when_supported() -> None:
    """Test get_api uses login_method for newer librouteros signatures."""
    entry = dict(MOCK_DATA)
    mock_connect = MagicMock(return_value=MagicMock())
    mock_connect.__signature__ = inspect.Signature(
        parameters=[
            inspect.Parameter("host", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("username", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter("password", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            inspect.Parameter(
                "login_method", inspect.Parameter.KEYWORD_ONLY, default=None
            ),
        ]
    )

    with patch(
        "homeassistant.components.mikrotik.coordinator.librouteros.connect",
        mock_connect,
    ):
        mikrotik.coordinator.get_api(entry)

    assert "login_method" in mock_connect.call_args.kwargs
    assert "login_methods" not in mock_connect.call_args.kwargs
    assert (
        mock_connect.call_args.kwargs["login_method"]
        is mikrotik.coordinator._login_method_with_fallback
    )
