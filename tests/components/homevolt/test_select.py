"""Tests for the Homevolt select platform."""

from unittest.mock import MagicMock

from homevolt import HomevoltConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "select.homevolt_ems_battery_mode"


@pytest.fixture
def platforms(mock_homevolt_client: MagicMock) -> list[Platform]:
    """Load the select platform with manual control enabled."""
    mock_homevolt_client.local_mode_enabled = True
    return [Platform.SELECT]


async def test_select_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the battery mode select."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_select_option(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test a command publishes the verified mode before returning."""

    async def set_battery_mode(*, mode: str) -> None:
        mock_homevolt_client.schedule["mode"] = 0

    mock_homevolt_client.set_battery_mode.side_effect = set_battery_mode
    mock_homevolt_client.update_info.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "idle"},
        blocking=True,
    )

    mock_homevolt_client.set_battery_mode.assert_awaited_once_with(mode="idle")
    mock_homevolt_client.update_info.assert_not_awaited()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "idle"


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(None, id="missing"),
        pytest.param(3, id="unsupported"),
    ],
)
async def test_select_unknown_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    mode: int | None,
) -> None:
    """Test missing and unsupported modes are unknown."""
    mock_homevolt_client.schedule["mode"] = mode

    await init_integration.runtime_data.async_request_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_select_unavailable_without_local_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test mode changes are unavailable until local mode is enabled."""
    mock_homevolt_client.local_mode_enabled = False

    await init_integration.runtime_data.async_request_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_select_option_error(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test select actions use the shared exception handler."""
    mock_homevolt_client.set_battery_mode.side_effect = HomevoltConnectionError(
        "connection failed"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "solar_charge"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "communication_error"
