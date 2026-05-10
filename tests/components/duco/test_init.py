"""Tests for the Duco integration setup."""

from ssl import SSLContext
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from duco.exceptions import DucoConnectionError, DucoError
from duco.models import BoardInfo, DiagComponent, DiagStatus, LanInfo, Node
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("method", "exception", "expected_state"),
    [
        (
            "async_get_board_info",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "async_get_board_info",
            DucoError("Unexpected API error"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "async_get_nodes",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    method: str,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test that fetch errors during setup result in the correct state."""
    getattr(mock_duco_client, method).side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


@pytest.mark.usefixtures("mock_duco_client")
async def test_setup_entry_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful setup of the Duco integration."""
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the Duco integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_builds_ssl_context_in_executor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_board_info: BoardInfo,
    mock_lan_info: LanInfo,
    mock_nodes: list[Node],
) -> None:
    """Test that build_ssl_context runs in an executor and its result is passed to DucoClient."""
    mock_ssl_context = MagicMock(spec=SSLContext)
    with (
        patch(
            "homeassistant.components.duco.build_ssl_context",
            return_value=mock_ssl_context,
        ) as mock_build,
        patch(
            "homeassistant.components.duco.DucoClient",
            autospec=True,
        ) as mock_client_class,
    ):
        mock_client_class.return_value.async_get_board_info.return_value = (
            mock_board_info
        )
        mock_client_class.return_value.async_get_lan_info.return_value = mock_lan_info
        mock_client_class.return_value.async_get_nodes.return_value = mock_nodes
        mock_client_class.return_value.async_get_diagnostics.return_value = [
            DiagComponent(component="Ventilation", status=DiagStatus.OK)
        ]
        mock_client_class.return_value.async_get_write_req_remaining.return_value = 100
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_build.assert_called_once()
    mock_client_class.assert_called_once_with(
        session=ANY,
        host=TEST_HOST,
        ssl_context=mock_ssl_context,
    )
