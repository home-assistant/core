"""Tests for the Duco fan platform."""

from unittest.mock import AsyncMock, patch

from duco.exceptions import DucoConnectionError, DucoError, DucoRateLimitError
from duco.models import (
    Node,
    NodeGeneralInfo,
    NodeSensorInfo,
    NodeVentilationInfo,
    VentilationState,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duco.const import SCAN_INTERVAL
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

_FAN_ENTITY = "fan.living"


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up only the fan platform for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.duco.PLATFORMS", [Platform.FAN]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry


@pytest.mark.usefixtures("init_integration")
async def test_fan_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the fan entity is created with the correct state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "service_data", "expected_duco_state"),
    [
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 0}, "AUTO"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 33}, "CNT1"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 66}, "CNT2"),
        (SERVICE_SET_PERCENTAGE, {ATTR_PERCENTAGE: 100}, "CNT3"),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "auto"}, "AUTO"),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "man1"}, "MAN1"),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "man2"}, "MAN2"),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "man3"}, "MAN3"),
        (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: "empt"}, "EMPT"),
    ],
)
async def test_fan_set_state(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    service: str,
    service_data: dict,
    expected_duco_state: str,
) -> None:
    """Test that fan service calls map to the correct Duco ventilation state."""
    mock_duco_client.async_set_ventilation_state = AsyncMock()

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: _FAN_ENTITY, **service_data},
        blocking=True,
    )

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(
        1, expected_duco_state
    )


def _box_node_with_state(state: VentilationState) -> Node:
    """Return a BOX node fixture with the given ventilation state."""
    return Node(
        node_id=1,
        general=NodeGeneralInfo(
            node_type="BOX",
            sub_type=1,
            network_type="VIRT",
            parent=0,
            asso=0,
            name="Living",
            identify=0,
        ),
        ventilation=NodeVentilationInfo(
            state=state.value,
            time_state_remain=0,
            time_state_end=0,
            mode="AUTO",
            flow_lvl_tgt=0,
        ),
        sensor=NodeSensorInfo(
            co2=None,
            iaq_co2=None,
            rh=None,
            iaq_rh=None,
            temp=27.9,
        ),
    )


@pytest.mark.parametrize(
    ("ventilation_state", "expected_preset", "expected_percentage"),
    [
        (VentilationState.AUTO, "auto", None),
        (VentilationState.AUT1, "auto", None),
        (VentilationState.AUT2, "auto", None),
        (VentilationState.AUT3, "auto", None),
        (VentilationState.MAN1, "man1", None),
        (VentilationState.MAN1x2, "man1", None),
        (VentilationState.MAN1x3, "man1", None),
        (VentilationState.MAN2, "man2", None),
        (VentilationState.MAN2x2, "man2", None),
        (VentilationState.MAN2x3, "man2", None),
        (VentilationState.MAN3, "man3", None),
        (VentilationState.MAN3x2, "man3", None),
        (VentilationState.MAN3x3, "man3", None),
        (VentilationState.EMPT, "empt", None),
        (VentilationState.CNT1, None, 33),
        (VentilationState.CNT2, None, 66),
        (VentilationState.CNT3, None, 100),
    ],
)
async def test_fan_read_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    ventilation_state: VentilationState,
    expected_preset: str | None,
    expected_percentage: int | None,
) -> None:
    """Test that preset_mode and percentage reflect the reported VentilationState."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.duco.PLATFORMS", [Platform.FAN]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    updated_nodes = [_box_node_with_state(ventilation_state), *mock_nodes[1:]]
    mock_duco_client.async_get_nodes = AsyncMock(return_value=updated_nodes)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_FAN_ENTITY)
    assert state is not None
    assert state.attributes.get("preset_mode") == expected_preset
    assert state.attributes.get("percentage") == expected_percentage


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (DucoConnectionError("Connection refused"), "Failed to set ventilation state"),
        (DucoError("Unexpected error"), "Failed to set ventilation state"),
        (DucoRateLimitError(), "daily write limit"),
    ],
)
async def test_fan_set_state_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    match: str,
) -> None:
    """Test that a HomeAssistantError is raised on API failure."""
    mock_duco_client.async_set_ventilation_state = AsyncMock(side_effect=exception)

    with pytest.raises(HomeAssistantError, match=match):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: _FAN_ENTITY, ATTR_PERCENTAGE: 100},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_fan_set_state_rate_limit_logs_warning(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a warning is logged when the write rate limit is exceeded."""
    mock_duco_client.async_set_ventilation_state = AsyncMock(
        side_effect=DucoRateLimitError()
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: _FAN_ENTITY, ATTR_PERCENTAGE: 100},
            blocking=True,
        )

    assert "write rate limit exceeded" in caplog.text


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(_FAN_ENTITY)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
