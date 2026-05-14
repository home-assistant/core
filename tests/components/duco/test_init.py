"""Tests for the Duco integration setup."""

from unittest.mock import ANY, AsyncMock, patch

from duco_connectivity import (
    BoardInfo,
    DiagComponent,
    DiagStatus,
    DucoConnectionError,
    DucoError,
    DucoResponseError,
    LanInfo,
    Node,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_HOST, TEST_MAC

from tests.common import MockConfigEntry

_UNSUPPORTED_BOARD_INFOS = [
    pytest.param(
        BoardInfo(
            box_name="ENERGY",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version="2.5",
        ),
        id="energy-not-supported",
    ),
    pytest.param(
        BoardInfo(
            box_name="FOCUS",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version="2.5",
        ),
        id="focus-not-supported",
    ),
    pytest.param(
        BoardInfo(
            box_name="SILENT_CONNECT",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version="2.0",
        ),
        id="version-too-low",
    ),
    pytest.param(
        BoardInfo(
            box_name="SILENT_CONNECT",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version=None,
        ),
        id="missing-version",
    ),
]


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


@pytest.mark.parametrize("unsupported_board_info", _UNSUPPORTED_BOARD_INFOS)
async def test_setup_entry_unsupported_board_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    unsupported_board_info: BoardInfo,
) -> None:
    """Test that unsupported board info blocks setup for existing entries."""
    mock_duco_client.async_get_board_info.return_value = unsupported_board_info
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_unsupported_board_without_info_endpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test that boards without the /info endpoint are rejected during setup."""
    mock_duco_client.async_get_board_info.side_effect = DucoResponseError(404, "/info")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test unloading the Duco integration."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_duco_client")
async def test_cleanup_orphaned_temperature_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that stale temperature entity entries from prior versions are removed on setup."""
    mock_config_entry.add_to_hass(hass)

    old_unique_ids = [
        f"{TEST_MAC}_1_box_temperature",
        f"{TEST_MAC}_2_temperature",
    ]
    for unique_id in old_unique_ids:
        entity_registry.async_get_or_create(
            Platform.SENSOR,
            "duco",
            unique_id,
            config_entry=mock_config_entry,
        )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for unique_id in old_unique_ids:
        assert (
            entity_registry.async_get_entity_id(Platform.SENSOR, "duco", unique_id)
            is None
        )


async def test_setup_entry_creates_http_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_board_info: BoardInfo,
    mock_lan_info: LanInfo,
    mock_nodes: list[Node],
) -> None:
    """Test that setup creates the Duco client with the provided host."""
    with patch(
        "homeassistant.components.duco.DucoClient",
        autospec=True,
    ) as mock_client_class:
        mock_client_class.return_value.async_get_board_info.return_value = (
            mock_board_info
        )
        mock_client_class.return_value.async_get_lan_info.return_value = mock_lan_info
        mock_client_class.return_value.async_get_nodes.return_value = mock_nodes
        mock_client_class.return_value.async_get_diagnostics.return_value = [
            DiagComponent(component="Ventilation", status=DiagStatus.OK)
        ]
        mock_client_class.return_value.async_get_write_requests_remaining.return_value = 100
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_client_class.assert_called_once_with(
        session=ANY,
        host=TEST_HOST,
    )
