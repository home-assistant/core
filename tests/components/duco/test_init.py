"""Tests for the Duco integration setup."""

from datetime import timedelta
from unittest.mock import ANY, AsyncMock, patch

from duco_connectivity import (
    BoardInfo,
    BypassSupplyTemperatureTarget,
    ConfigNode,
    ConfigNodeOverview,
    ConfigValueString,
    DiagComponent,
    DucoConnectionError,
    DucoError,
    DucoResponseError,
    LanInfo,
    Node,
    NodeListActionItemList,
    VentilationTemperatureInfo,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.duco.const import BOX_NODE_ID, DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_platform_integration
from .conftest import (
    TEST_HOST,
    TEST_MAC,
    UNSUPPORTED_BOARD_INFOS,
    node_configs_from_nodes,
)

from tests.common import MockConfigEntry, async_fire_time_changed


def _get_duco_node_device(
    device_registry: dr.DeviceRegistry, config_entry_id: str
) -> dr.DeviceEntry:
    """Return the primary Duco node device used in setup tests."""
    device = device_registry.async_get_device_by_identifier(
        ("duco", f"{TEST_MAC}_1"), config_entry_id
    )
    assert device is not None
    return device


def _node_configs_with_primary_name(
    mock_nodes: list[Node],
    primary_name: str,
) -> ConfigNodeOverview:
    """Return node configs with a custom name for the primary Duco node."""
    return ConfigNodeOverview(
        nodes=[
            ConfigNode(node_id=1, name=ConfigValueString(primary_name)),
            *node_configs_from_nodes(mock_nodes[1:]).nodes,
        ]
    )


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
            "cannot_connect",
            False,
        ),
        (
            "async_get_board_info",
            DucoError("Unexpected API error"),
            ConfigEntryState.SETUP_ERROR,
            "api_error",
            False,
        ),
        (
            "async_get_board_info",
            DucoResponseError(500, "/info"),
            ConfigEntryState.SETUP_ERROR,
            "api_error",
            False,
        ),
        (
            "async_get_nodes",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
            False,
        ),
        (
            "async_get_node_actions",
            DucoConnectionError("Connection refused"),
            ConfigEntryState.LOADED,
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


async def test_device_via_device_links(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a sub-node added before the box still links to it via via_device_id."""
    # Force the child-before-parent race: return a sub-node ahead of the box node
    # and set up only the sensor platform (the fan platform would otherwise create
    # the box first). This only resolves because the box is pre-registered in
    # async_setup_entry before the platforms build their entities.
    box_node = next(node for node in mock_nodes if node.node_id == BOX_NODE_ID)
    child_node = next(node for node in mock_nodes if node.node_id != BOX_NODE_ID)
    mock_duco_client.async_get_nodes.return_value = [child_node, box_node]

    await setup_platform_integration(hass, mock_config_entry, [Platform.SENSOR])

    box_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{TEST_MAC}_{BOX_NODE_ID}"), mock_config_entry.entry_id
    )
    assert box_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{TEST_MAC}_{child_node.node_id}"), mock_config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == box_device.id


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


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(DucoError("API error"), id="duco_error"),
        pytest.param(DucoConnectionError("Connection refused"), id="connection_error"),
    ],
)
async def test_setup_entry_recovers_from_optional_temperature_capability_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    exception: Exception,
) -> None:
    """Test an optional temperature capability is retried after a setup failure."""
    mock_duco_client.async_get_ventilation_temperature_info.side_effect = [
        exception,
        VentilationTemperatureInfo(temp_oda=5.5),
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.living_outdoor_air_temperature") is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.living_outdoor_air_temperature")
    assert state is not None
    assert state.state == "5.5"


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(
            DucoConnectionError("Connection refused"),
            "cannot_connect",
            id="connection_error",
        ),
        pytest.param(DucoError("API error"), "api_error", id="duco_error"),
        pytest.param(
            DucoResponseError(500, "/config"),
            "api_error",
            id="response_error",
        ),
    ],
)
async def test_setup_entry_retries_on_bypass_temperature_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test setup retries when fetching bypass temperature targets fails."""
    mock_duco_client.async_get_bypass_supply_temperature_targets.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders is None


async def test_empty_bypass_temperature_targets_are_retried(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test empty bypass targets are retried and can later create entities."""
    mock_duco_client.async_get_bypass_supply_temperature_targets.side_effect = [
        {},
        mock_bypass_supply_temperature_targets.copy(),
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("number.living_bypass_target_1") is None
    assert hass.states.get("number.living_bypass_target_2") is None
    mock_duco_client.async_get_bypass_supply_temperature_targets.assert_awaited_once_with()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_duco_client.async_get_bypass_supply_temperature_targets.await_count == 2
    assert hass.states.get("number.living_bypass_target_1") is not None
    assert hass.states.get("number.living_bypass_target_2") is not None


async def test_missing_bypass_temperature_targets_are_retried(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bypass_supply_temperature_targets: dict[int, BypassSupplyTemperatureTarget],
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test missing bypass targets are retried and can later create entities."""
    targets_without_zone_1 = {
        k: v for k, v in mock_bypass_supply_temperature_targets.items() if k != 1
    }
    mock_duco_client.async_get_bypass_supply_temperature_targets.side_effect = [
        targets_without_zone_1,
        mock_bypass_supply_temperature_targets.copy(),
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("number.living_bypass_target_1") is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("number.living_bypass_target_1")
    assert state is not None
    assert state.state == "20.0"


async def test_setup_entry_ignores_node_name_config_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup falls back to API node names when node config fetch fails."""
    mock_duco_client.async_get_node_configs.side_effect = DucoError("node config error")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device = _get_duco_node_device(device_registry, mock_config_entry.entry_id)
    assert device.name == mock_nodes[0].general.name
    assert mock_duco_client.async_get_node_configs.call_count == 1


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
    mock_node_actions: NodeListActionItemList,
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
        mock_client_class.return_value.async_get_node_actions.return_value = (
            mock_node_actions
        )
        (
            mock_client_class.return_value.async_get_ventilation_temperature_info.return_value
        ) = VentilationTemperatureInfo()

        mock_client_class.return_value.async_get_bypass_supply_temperature_targets.return_value = {
            1: BypassSupplyTemperatureTarget(
                zone_id=1,
                value=20.0,
                minimum=15.0,
                increment=0.1,
                maximum=25.0,
            )
        }
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


async def test_setup_entry_uses_configured_node_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup uses the configurable Duco node name."""
    mock_duco_client.async_get_node_configs.return_value = (
        _node_configs_with_primary_name(mock_nodes, "Kitchen")
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = _get_duco_node_device(device_registry, mock_config_entry.entry_id)
    assert device.name == "Kitchen"
    assert mock_duco_client.async_get_node_configs.call_count == 1


async def test_node_name_refresh_updates_device_registry_name(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Duco node names update on reload, not during periodic polling."""
    mock_duco_client.async_get_node_configs.side_effect = [
        _node_configs_with_primary_name(mock_nodes, "Kitchen"),
        _node_configs_with_primary_name(mock_nodes, "Living Room"),
    ]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = _get_duco_node_device(device_registry, mock_config_entry.entry_id)
    assert device.name == "Kitchen"
    assert mock_duco_client.async_get_node_configs.call_count == 1

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = _get_duco_node_device(device_registry, mock_config_entry.entry_id)
    assert device.name == "Kitchen"
    assert mock_duco_client.async_get_node_configs.call_count == 1

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = _get_duco_node_device(device_registry, mock_config_entry.entry_id)
    assert device.name == "Living Room"
    assert mock_duco_client.async_get_node_configs.call_count == 2
