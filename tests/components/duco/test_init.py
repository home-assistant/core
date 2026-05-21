"""Tests for the Duco integration setup."""

from dataclasses import replace
from unittest.mock import ANY, AsyncMock, patch

from duco_connectivity import (
    BoardInfo,
    DiagComponent,
    DucoConnectionError,
    DucoError,
    DucoResponseError,
    InfoGroup,
    InfoZone,
    InfoZonesOverview,
    LanInfo,
    Node,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.duco.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import TEST_HOST, TEST_MAC, UNSUPPORTED_BOARD_INFOS

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    (
        "method",
        "exception",
        "expected_state",
        "expected_translation_key",
        "has_error_translation_placeholder",
    ),
    [
        (
            "async_get_board_info",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
            None,
            False,
        ),
        (
            "async_get_board_info",
            DucoError("Unexpected API error"),
            ConfigEntryState.SETUP_ERROR,
            "api_error",
            True,
        ),
        (
            "async_get_board_info",
            DucoResponseError(500, "/info"),
            ConfigEntryState.SETUP_ERROR,
            "api_error",
            True,
        ),
        (
            "async_get_nodes",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
            None,
            False,
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
    expected_translation_key: str | None,
    has_error_translation_placeholder: bool,
) -> None:
    """Test that fetch errors during setup result in the correct state."""
    getattr(mock_duco_client, method).side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert mock_config_entry.error_reason_translation_key == expected_translation_key
    if has_error_translation_placeholder:
        assert mock_config_entry.error_reason_translation_placeholders == {
            "error": repr(exception)
        }
    else:
        assert mock_config_entry.error_reason_translation_placeholders is None


@pytest.mark.usefixtures("mock_duco_client")
async def test_setup_entry_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful setup of the Duco integration."""
    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(DucoError("lan info error"), id="duco_error"),
        pytest.param(DucoConnectionError("lan info offline"), id="connection_error"),
    ],
)
async def test_setup_entry_ignores_lan_info_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test setup succeeds when the supplemental LAN info endpoint fails."""
    mock_duco_client.async_get_lan_info.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("unsupported_board_info", UNSUPPORTED_BOARD_INFOS)
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
    assert mock_config_entry.error_reason_translation_key == "unsupported_board"
    assert mock_config_entry.error_reason_translation_placeholders is None


async def test_setup_entry_unsupported_board_without_info_endpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test that setup fails when the board does not expose /info."""
    mock_duco_client.async_get_board_info.side_effect = DucoResponseError(404, "/info")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "unsupported_board"
    assert mock_config_entry.error_reason_translation_placeholders is None


@pytest.mark.usefixtures("init_integration")
async def test_devices_registered_with_expected_metadata(
    device_registry: dr.DeviceRegistry,
    mock_board_info: BoardInfo,
) -> None:
    """Test that the Duco box and node devices expose the expected metadata."""
    box_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_1")}
    )
    assert box_device is not None
    assert box_device.configuration_url == f"http://{TEST_HOST}"
    assert box_device.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC)}
    assert box_device.manufacturer == "Duco"
    assert box_device.model == mock_board_info.box_name
    assert box_device.model_id == mock_board_info.box_sub_type_name
    assert box_device.name == "Living"
    assert box_device.serial_number == mock_board_info.serial_board_box
    assert box_device.sw_version == mock_board_info.software_version
    assert box_device.via_device_id is None

    child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert child_device is not None
    assert (
        child_device.configuration_url
        == f"http://{TEST_HOST}/nodeconfig.html?node=2&zone=1&group=1"
    )
    assert child_device.connections == set()
    assert child_device.manufacturer == "Duco"
    assert child_device.model == "UCCO2"
    assert child_device.name == "Office CO2"
    assert child_device.via_device_id == box_device.id

    unmatched_child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_50")}
    )
    assert unmatched_child_device is not None
    assert unmatched_child_device.configuration_url is None


async def test_box_device_name_falls_back_to_box_name_when_node_name_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that an unnamed box node uses the board box name as device name."""
    mock_duco_client.async_get_nodes.return_value = [
        replace(
            mock_nodes[0],
            general=replace(mock_nodes[0].general, name=""),
        ),
        *mock_nodes[1:],
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    box_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_1")}
    )
    assert box_device is not None
    assert box_device.name == "SILENT_CONNECT"


async def test_child_device_visit_link_omitted_for_ambiguous_zone_matches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_zones_info: InfoZonesOverview,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that child devices get no visit link when multiple matches exist."""
    mock_duco_client.async_get_zones_info.return_value = InfoZonesOverview(
        zones=[
            *mock_zones_info.zones,
            InfoZone(
                zone_id=2,
                name="Second zone",
                groups=[InfoGroup(group_id=2, nodes=[2])],
            ),
        ]
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert child_device is not None
    assert child_device.configuration_url is None


async def test_child_device_visit_link_kept_for_duplicate_zone_memberships(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that duplicate node entries in one group keep the visit link."""
    mock_duco_client.async_get_zones_info.return_value = InfoZonesOverview(
        zones=[
            InfoZone(
                zone_id=1,
                name="VentEtaCentral",
                groups=[InfoGroup(group_id=1, nodes=[2, 2, 113])],
            )
        ]
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert child_device is not None
    assert (
        child_device.configuration_url
        == f"http://{TEST_HOST}/nodeconfig.html?node=2&zone=1&group=1"
    )


async def test_child_device_visit_link_added_after_later_successful_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_zones_info: InfoZonesOverview,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a later successful zones refresh updates the device visit link."""
    mock_duco_client.async_get_zones_info.side_effect = [
        DucoConnectionError("offline"),
        mock_zones_info,
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert child_device is not None
    assert child_device.configuration_url is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    refreshed_child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert refreshed_child_device is not None
    assert (
        refreshed_child_device.configuration_url
        == f"http://{TEST_HOST}/nodeconfig.html?node=2&zone=1&group=1"
    )


async def test_child_device_visit_link_preserved_after_zones_parse_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_duco_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a later zones parse error does not remove the existing visit link."""
    child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert child_device is not None
    assert (
        child_device.configuration_url
        == f"http://{TEST_HOST}/nodeconfig.html?node=2&zone=1&group=1"
    )

    mock_duco_client.async_get_zones_info.side_effect = DucoError("bad zones")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    refreshed_child_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{TEST_MAC}_2")}
    )
    assert refreshed_child_device is not None
    assert (
        refreshed_child_device.configuration_url
        == f"http://{TEST_HOST}/nodeconfig.html?node=2&zone=1&group=1"
    )


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
    """Test stale temperature entities from prior versions are removed on setup."""
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
    mock_zones_info: InfoZonesOverview,
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
        mock_client_class.return_value.async_get_zones_info.return_value = (
            mock_zones_info
        )
        mock_client_class.return_value.async_get_diagnostics.return_value = [
            DiagComponent(component="Ventilation", status="Ok")
        ]
        (
            mock_client_class.return_value.async_get_write_requests_remaining
        ).return_value = 100
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_client_class.assert_called_once_with(
        session=ANY,
        host=TEST_HOST,
    )
