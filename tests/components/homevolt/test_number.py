"""Tests for the Homevolt number platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homevolt import HomevoltConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homevolt.const import SCAN_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SETPOINT_ENTITY_ID = "number.homevolt_ems_power_setpoint"
IMPORT_LIMIT_ENTITY_ID = "number.homevolt_ems_grid_import_limit"
EXPORT_LIMIT_ENTITY_ID = "number.homevolt_ems_grid_export_limit"


@pytest.fixture
def platforms(mock_homevolt_client: MagicMock) -> list[Platform]:
    """Load the number platform with a writable manual schedule."""
    mock_homevolt_client.local_mode_enabled = True
    mock_homevolt_client.writable_battery_parameters = frozenset({"setpoint"})
    return [Platform.NUMBER]


async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test battery control number states and registry entries."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("key", "entity_id", "value", "mode"),
    [
        pytest.param("setpoint", SETPOINT_ENTITY_ID, 1000, 1, id="setpoint"),
        pytest.param(
            "grid_import_limit", IMPORT_LIMIT_ENTITY_ID, 4000, 6, id="import-limit"
        ),
        pytest.param(
            "grid_export_limit", EXPORT_LIMIT_ENTITY_ID, 5000, 6, id="export-limit"
        ),
    ],
)
async def test_set_number_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    key: str,
    entity_id: str,
    value: int,
    mode: int,
) -> None:
    """Test each supported parameter publishes its verified value immediately."""
    mock_homevolt_client.schedule["mode"] = mode
    mock_homevolt_client.writable_battery_parameters = frozenset({key})
    init_integration.runtime_data.async_update_listeners()

    async def set_battery_parameters(**parameters: int) -> None:
        mock_homevolt_client.schedule.update(parameters)

    mock_homevolt_client.set_battery_parameters.side_effect = set_battery_parameters
    mock_homevolt_client.update_info.reset_mock()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_homevolt_client.set_battery_parameters.assert_awaited_once_with(**{key: value})
    mock_homevolt_client.update_info.assert_not_awaited()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == str(float(value))


async def test_number_unknown_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test an absent manual parameter has an unknown state."""
    mock_homevolt_client.schedule["setpoint"] = None
    await init_integration.runtime_data.async_request_refresh()

    state = hass.states.get(SETPOINT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_numbers_unavailable_without_writable_manual_schedule(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test parameter writes are unavailable for non-manual schedules."""
    mock_homevolt_client.writable_battery_parameters = frozenset()
    await init_integration.runtime_data.async_request_refresh()

    state = hass.states.get(SETPOINT_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "value",
    [pytest.param(-1, id="below-minimum"), pytest.param(11001, id="above-maximum")],
)
async def test_invalid_number_value(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    value: int,
) -> None:
    """Test out-of-range values never reach the client."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SETPOINT_ENTITY_ID, ATTR_VALUE: value},
            blocking=True,
        )

    mock_homevolt_client.set_battery_parameters.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_number_value_error(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test number actions use the shared translated error handler."""
    mock_homevolt_client.set_battery_parameters.side_effect = HomevoltConnectionError(
        "Connection failed"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SETPOINT_ENTITY_ID, ATTR_VALUE: 1000},
            blocking=True,
        )

    assert exc_info.value.translation_key == "communication_error"
    assert exc_info.value.translation_placeholders == {"error": "Connection failed"}


async def test_commands_preserve_telemetry_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test repeated schedule writes do not postpone the regular telemetry poll."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.homevolt.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_homevolt_client.update_info.assert_awaited_once()
    mock_homevolt_client.update_info.reset_mock()
    command_interval = SCAN_INTERVAL / 3

    for _ in range(2):
        freezer.tick(command_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SETPOINT_ENTITY_ID, ATTR_VALUE: 1000},
            blocking=True,
        )
        mock_homevolt_client.update_info.assert_not_awaited()

    freezer.tick(command_interval.total_seconds() + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_homevolt_client.update_info.assert_awaited_once()
