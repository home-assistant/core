"""Tests for the Homevolt select platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homevolt import HomevoltAuthenticationError, HomevoltConnectionError, HomevoltError
from homevolt.const import CONTROLLABLE_SCHEDULE_TYPE
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homevolt.const import SCAN_INTERVAL
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
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "select.homevolt_ems_battery_mode"
MODE_BY_OPTION = {option: mode for mode, option in CONTROLLABLE_SCHEDULE_TYPE.items()}


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

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "inverter_charge"
    assert state.attributes["options"] == list(CONTROLLABLE_SCHEDULE_TYPE.values())


@pytest.mark.parametrize(("mode", "option"), list(CONTROLLABLE_SCHEDULE_TYPE.items()))
@pytest.mark.usefixtures("init_integration")
async def test_select_option(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    mode: int,
    option: str,
) -> None:
    """Test every supported battery mode command."""

    async def set_battery_mode(*, mode: str) -> None:
        mock_homevolt_client.schedule["mode"] = MODE_BY_OPTION[mode]

    mock_homevolt_client.set_battery_mode.side_effect = set_battery_mode
    mock_homevolt_client.set_battery_mode.reset_mock()
    mock_homevolt_client.update_info.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    mock_homevolt_client.set_battery_mode.assert_awaited_once_with(mode=option)
    mock_homevolt_client.update_info.assert_not_awaited()
    assert mock_homevolt_client.schedule["mode"] == mode
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == option


@pytest.mark.usefixtures("init_integration")
async def test_consecutive_select_options_refresh_state_immediately(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test consecutive commands publish the verified state before returning."""

    async def set_battery_mode(mode: str) -> None:
        mock_homevolt_client.schedule["mode"] = {
            "inverter_charge": 1,
            "idle": 0,
        }[mode]

    mock_homevolt_client.set_battery_mode.side_effect = set_battery_mode

    for option in ("inverter_charge", "idle"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
            blocking=True,
        )

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == option


async def test_select_unknown_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test a missing schedule mode is unknown, not idle."""
    mock_homevolt_client.schedule["mode"] = None

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
async def test_invalid_select_option(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test invalid options never reach the client."""
    mock_homevolt_client.set_battery_mode.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "invalid"},
            blocking=True,
        )

    mock_homevolt_client.set_battery_mode.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "expected_exception", "translation_key", "placeholders"),
    [
        (
            HomevoltAuthenticationError("auth failed"),
            ConfigEntryAuthFailed,
            "auth_failed",
            None,
        ),
        (
            HomevoltConnectionError("connection failed"),
            HomeAssistantError,
            "communication_error",
            {"error": "connection failed"},
        ),
        (
            HomevoltError("unknown error"),
            HomeAssistantError,
            "unknown_error",
            {"error": "unknown error"},
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_error(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    exception: HomevoltError,
    expected_exception: type[Exception],
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test translated client errors when selecting a mode."""
    mock_homevolt_client.set_battery_mode.side_effect = exception
    mock_homevolt_client.update_info.reset_mock()

    with pytest.raises(expected_exception) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "solar_charge"},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == placeholders
    mock_homevolt_client.update_info.assert_not_awaited()


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
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "inverter_charge"},
            blocking=True,
        )
        mock_homevolt_client.update_info.assert_not_awaited()

    freezer.tick(command_interval.total_seconds() + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_homevolt_client.update_info.assert_awaited_once()
