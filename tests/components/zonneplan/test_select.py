"""Tests for the Zonneplan select platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pyzonneplan import (
    BatteryControlMode,
    BatteryControlModeOption,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanRateLimitError,
    ZonneplanRequestError,
    ZonneplanTimeoutError,
)
from pyzonneplan.const import BatteryMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.zonneplan.const import DOMAIN
from homeassistant.components.zonneplan.coordinator import (
    BATTERY_CONTROL_UPDATE_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

CONTROL_MODE_ENTITY_ID = "select.thuisbatterij_control_mode"
CONNECTION_UUID = "00000000-0000-4000-8000-000000000002"
CONTRACT_UUID = "00000000-0000-4000-8000-000000000201"


@pytest.fixture(autouse=True)
def select_only() -> Generator[None]:
    """Set up only the select platform."""
    with patch("homeassistant.components.zonneplan.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_select(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("control_mode", "expected_options"),
    [
        pytest.param(
            BatteryMode.SELF_CONSUMPTION,
            ["self_consumption", "home_optimization"],
            id="available_modes_only",
        ),
        pytest.param(
            BatteryMode.DYNAMIC_CHARGING,
            ["self_consumption", "home_optimization", "dynamic_charging"],
            id="current_mode_unavailable",
        ),
    ],
)
async def test_select_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    control_mode: BatteryMode,
    expected_options: list[str],
) -> None:
    """Test the options are the available modes, plus the current one."""
    mock_zonneplan_client.async_get_battery_control_mode.return_value = (
        BatteryControlMode(
            control_mode=control_mode,
            modes={
                "self_consumption": BatteryControlModeOption(available=True),
                "home_optimization": BatteryControlModeOption(available=True),
                "dynamic_charging": BatteryControlModeOption(available=False),
                "day_ahead_arbitrage": BatteryControlModeOption(available=False),
            },
        )
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == control_mode
    assert state.attributes[ATTR_OPTIONS] == expected_options


@pytest.mark.usefixtures("init_integration")
async def test_select_option(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test selecting a control mode switches the battery and refreshes."""
    assert mock_zonneplan_client.async_get_battery_control_mode.call_count == 1
    mock_zonneplan_client.async_get_battery_control_mode.return_value.control_mode = (
        BatteryMode.HOME_OPTIMIZATION
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CONTROL_MODE_ENTITY_ID, ATTR_OPTION: "home_optimization"},
        blocking=True,
    )

    mock_zonneplan_client.async_set_battery_control_mode.assert_awaited_once_with(
        CONNECTION_UUID, CONTRACT_UUID, BatteryMode.HOME_OPTIMIZATION
    )
    assert mock_zonneplan_client.async_get_battery_control_mode.call_count == 2
    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == "home_optimization"


@pytest.mark.usefixtures("init_integration")
async def test_select_unavailable_option(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test a mode the battery doesn't support can't be selected."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: CONTROL_MODE_ENTITY_ID,
                ATTR_OPTION: "day_ahead_arbitrage",
            },
            blocking=True,
        )

    mock_zonneplan_client.async_set_battery_control_mode.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "expected_exception", "translation_key"),
    [
        pytest.param(
            ValueError("Day-ahead arbitrage has no settings yet"),
            ServiceValidationError,
            "day_ahead_arbitrage_not_set_up",
            id="day_ahead_arbitrage_not_set_up",
        ),
        pytest.param(
            ZonneplanTimeoutError("timed out"),
            HomeAssistantError,
            "timeout_connect",
            id="timeout_error",
        ),
        pytest.param(
            ZonneplanConnectionError("boom"),
            HomeAssistantError,
            "cannot_connect",
            id="connection_error",
        ),
        pytest.param(
            ZonneplanRateLimitError("slow down", retry_after=30),
            HomeAssistantError,
            "rate_limited",
            id="rate_limit_error",
        ),
        pytest.param(
            ZonneplanRequestError("rejected"),
            HomeAssistantError,
            "api_error",
            id="request_error",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option_error(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    expected_exception: type[HomeAssistantError],
    translation_key: str,
) -> None:
    """Test errors while switching the control mode still refresh the control mode."""
    mock_zonneplan_client.async_set_battery_control_mode.side_effect = exception

    with pytest.raises(expected_exception) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: CONTROL_MODE_ENTITY_ID, ATTR_OPTION: "home_optimization"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    # The switch may have been applied partly, so the select shows what the battery reports.
    assert mock_zonneplan_client.async_get_battery_control_mode.call_count == 2


async def test_select_option_authentication_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test an authentication error while switching starts a reauth flow."""
    mock_zonneplan_client.async_set_battery_control_mode.side_effect = (
        ZonneplanAuthenticationError("bad token")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: CONTROL_MODE_ENTITY_ID, ATTR_OPTION: "home_optimization"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "invalid_auth"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id


@pytest.mark.usefixtures("init_integration")
async def test_select_update(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the select follows the control mode and is unavailable on errors."""
    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == "self_consumption"

    mock_zonneplan_client.async_get_battery_control_mode.side_effect = (
        ZonneplanConnectionError("boom")
    )
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    mock_zonneplan_client.async_get_battery_control_mode.side_effect = None
    mock_zonneplan_client.async_get_battery_control_mode.return_value.control_mode = (
        BatteryMode.DYNAMIC_CHARGING
    )
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == "dynamic_charging"


async def test_select_control_mode_unavailable_at_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing control mode doesn't block the setup."""
    mock_zonneplan_client.async_get_battery_control_mode.side_effect = (
        ZonneplanConnectionError("boom")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    mock_zonneplan_client.async_get_battery_control_mode.side_effect = None
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(CONTROL_MODE_ENTITY_ID))
    assert state.state == "self_consumption"
    assert state.attributes[ATTR_OPTIONS] == [
        "self_consumption",
        "home_optimization",
        "dynamic_charging",
    ]
