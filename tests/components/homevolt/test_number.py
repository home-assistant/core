"""Tests for the Homevolt number platform."""

from unittest.mock import MagicMock

from homevolt import (
    HomevoltAuthenticationError,
    HomevoltCommandOutcomeUnknownError,
    HomevoltCommandRejectedError,
    HomevoltCommandVerificationError,
    HomevoltConnectionError,
    HomevoltError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

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
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms(mock_homevolt_client: MagicMock) -> list[Platform]:
    """Load the number platform with a writable manual schedule."""
    mock_homevolt_client.local_mode_enabled = True
    mock_homevolt_client.current_schedule["local_mode"] = True
    mock_homevolt_client.battery_parameters_writable = True
    mock_homevolt_client.writable_battery_parameters = frozenset({"setpoint"})
    return [Platform.NUMBER]


async def test_number_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all battery control number entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_power_numbers_use_documented_conservative_limit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Do not advertise the previous unverified universal 20 kW range."""
    state = hass.states.get("number.homevolt_ems_power_setpoint")
    assert state is not None
    assert state.attributes["max"] == 11000


@pytest.mark.parametrize(
    ("key", "entity_id", "value", "expected_state"),
    [
        ("setpoint", "number.homevolt_ems_power_setpoint", 1000, "1000.0"),
    ],
)
async def test_set_number_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    key: str,
    entity_id: str,
    value: int,
    expected_state: str,
) -> None:
    """Test every supported battery parameter command."""

    async def set_battery_parameters(**parameters: int) -> None:
        mock_homevolt_client.schedule.update(parameters)

    mock_homevolt_client.set_battery_parameters.side_effect = set_battery_parameters
    mock_homevolt_client.set_battery_parameters.reset_mock()
    mock_homevolt_client.update_info.reset_mock()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_homevolt_client.set_battery_parameters.assert_awaited_once_with(**{key: value})
    mock_homevolt_client.update_info.assert_awaited_once_with()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("key", "entity_id", "value"),
    [
        ("grid_import_limit", "number.homevolt_ems_grid_import_limit", 4000),
        ("grid_export_limit", "number.homevolt_ems_grid_export_limit", 5000),
    ],
)
async def test_set_frequency_reserve_grid_limit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    key: str,
    entity_id: str,
    value: int,
) -> None:
    """Test independently verified frequency-reserve grid limits."""
    mock_homevolt_client.schedule["mode"] = 6
    mock_homevolt_client.writable_battery_parameters = frozenset(
        {"grid_import_limit", "grid_export_limit"}
    )

    async def set_battery_parameters(**parameters: int) -> None:
        mock_homevolt_client.schedule.update(parameters)

    mock_homevolt_client.set_battery_parameters.side_effect = set_battery_parameters
    mock_homevolt_client.set_battery_parameters.reset_mock()
    mock_homevolt_client.update_info.reset_mock()
    init_integration.runtime_data.async_set_updated_data(mock_homevolt_client)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    mock_homevolt_client.set_battery_parameters.assert_awaited_once_with(**{key: value})
    mock_homevolt_client.update_info.assert_awaited_once_with()


async def test_number_unknown_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test an absent manual parameter has an unknown state."""
    entity_id = "number.homevolt_ems_power_setpoint"
    mock_homevolt_client.schedule["setpoint"] = None

    await init_integration.runtime_data.async_request_refresh()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_numbers_unavailable_without_writable_manual_schedule(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test parameter writes are unavailable for non-manual schedules."""
    mock_homevolt_client.battery_parameters_writable = False
    mock_homevolt_client.writable_battery_parameters = frozenset()

    await init_integration.runtime_data.async_request_refresh()

    state = hass.states.get("number.homevolt_ems_power_setpoint")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_number_availability_is_parameter_specific(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Expose only parameters independently writable in the current mode."""
    mock_homevolt_client.writable_battery_parameters = frozenset({"setpoint"})

    await init_integration.runtime_data.async_request_refresh()

    setpoint = hass.states.get("number.homevolt_ems_power_setpoint")
    max_charge = hass.states.get("number.homevolt_ems_maximum_charge_power")
    assert setpoint is not None
    assert setpoint.state != STATE_UNAVAILABLE
    assert max_charge is not None
    assert max_charge.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("value", "entity_id"),
    [
        (-1, "number.homevolt_ems_power_setpoint"),
        (11001, "number.homevolt_ems_power_setpoint"),
    ],
)
async def test_invalid_number_value(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    value: int,
    entity_id: str,
) -> None:
    """Test out-of-range values never reach the client."""
    mock_homevolt_client.set_battery_parameters.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    mock_homevolt_client.set_battery_parameters.assert_not_awaited()


@pytest.mark.parametrize(
    (
        "exception",
        "expected_exception",
        "translation_key",
        "placeholders",
        "refresh_count",
    ),
    [
        (
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
            "auth_failed",
            None,
            0,
        ),
        (
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
            "communication_error",
            {"error": "connection failed"},
            0,
        ),
        (
            HomevoltCommandRejectedError("invalid command"),
            HomeAssistantError,
            "command_rejected",
            {"error": "invalid command"},
            0,
        ),
        (
            HomevoltCommandVerificationError("state mismatch"),
            HomeAssistantError,
            "command_verification_failed",
            {"error": "state mismatch"},
            1,
        ),
        (
            HomevoltCommandOutcomeUnknownError("read-back failed"),
            HomeAssistantError,
            "command_outcome_unknown",
            {"error": "read-back failed"},
            1,
        ),
        (
            HomevoltError("unknown error"),
            HomeAssistantError,
            "unknown_error",
            {"error": "unknown error"},
            0,
        ),
    ],
)
async def test_set_number_value_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
    exception: HomevoltError,
    expected_exception: type[Exception],
    translation_key: str,
    placeholders: dict[str, str] | None,
    refresh_count: int,
) -> None:
    """Test translated client errors when setting a number."""
    mock_homevolt_client.set_battery_parameters.side_effect = exception
    mock_homevolt_client.update_info.reset_mock()

    with pytest.raises(expected_exception) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.homevolt_ems_power_setpoint",
                ATTR_VALUE: 1000,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders
    assert mock_homevolt_client.update_info.await_count == refresh_count
