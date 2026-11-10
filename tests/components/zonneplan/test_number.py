"""Tests for the Zonneplan number platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, call, patch

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
    BatteryDayAheadArbitrage,
    BatteryHomeOptimization,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanRateLimitError,
    ZonneplanRequestError,
    ZonneplanTimeoutError,
)
from pyzonneplan.const import BatteryMode, MarketTimeResolution
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
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

MAX_CHARGE_POWER_ENTITY_ID = "number.thuisbatterij_maximum_charge_power"
MAX_DISCHARGE_POWER_ENTITY_ID = "number.thuisbatterij_maximum_discharge_power"
PRICE_SPREAD_ENTITY_ID = "number.thuisbatterij_minimum_price_spread"
BACKUP_RESERVE_ENTITY_ID = "number.thuisbatterij_backup_power_reserve"
CONNECTION_UUID = "00000000-0000-4000-8000-000000000002"
CONTRACT_UUID = "00000000-0000-4000-8000-000000000201"


def _control_mode(control_mode: BatteryMode, *, available: bool) -> BatteryControlMode:
    """Return a control mode response with every mode (un)available."""
    return BatteryControlMode(
        control_mode=control_mode,
        modes={
            mode.value: BatteryControlModeOption(
                enabled=mode == control_mode, available=available
            )
            for mode in BatteryMode
        },
    )


@pytest.fixture(autouse=True)
def number_only() -> Generator[None]:
    """Set up only the number platform."""
    with patch("homeassistant.components.zonneplan.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.fixture
def control_mode() -> BatteryMode:
    """Return the control mode the battery runs in."""
    return BatteryMode.HOME_OPTIMIZATION


@pytest.fixture(autouse=True)
def all_modes_available(
    mock_zonneplan_client: AsyncMock, control_mode: BatteryMode
) -> None:
    """Make every control mode available, so every setting is fetched."""
    mock_zonneplan_client.async_get_battery_control_mode.return_value = _control_mode(
        control_mode, available=True
    )


async def _set_value(hass: HomeAssistant, entity_id: str, value: float) -> None:
    """Set the value of a number entity."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the number entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_backup_reserve_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the backup reserve is disabled by default."""
    assert hass.states.get(BACKUP_RESERVE_ENTITY_ID) is None
    assert (entry := entity_registry.async_get(BACKUP_RESERVE_ENTITY_ID))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test settings of unavailable modes and backup power aren't created or fetched."""
    mock_zonneplan_client.async_get_battery_control_mode.return_value = _control_mode(
        BatteryMode.SELF_CONSUMPTION, available=False
    )
    battery = mock_zonneplan_client.async_get_battery.return_value.battery
    battery.contract.meta["backup_power_capable"] = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids(NUMBER_DOMAIN) == []
    mock_zonneplan_client.async_get_battery_home_optimization.assert_not_awaited()
    mock_zonneplan_client.async_get_battery_day_ahead_arbitrage.assert_not_awaited()


async def test_power_limit_range_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the power limits fall back to the app's range without limits."""
    mock_zonneplan_client.async_get_battery_home_optimization.return_value = (
        BatteryHomeOptimization(
            max_desired_charge_power_watts=2000,
            max_desired_discharge_power_watts=800,
        )
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(MAX_CHARGE_POWER_ENTITY_ID))
    assert state.attributes[ATTR_MIN] == 0
    assert state.attributes[ATTR_MAX] == 10000


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_backup_reserve_without_capacity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the backup reserve is unavailable without a usable capacity."""
    battery = mock_zonneplan_client.async_get_battery.return_value.battery
    battery.contract.meta["backup_power_usable_capacity_wh"] = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(BACKUP_RESERVE_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "entity_id", [MAX_CHARGE_POWER_ENTITY_ID, MAX_DISCHARGE_POWER_ENTITY_ID]
)
async def test_power_limits_unavailable_without_both(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    entity_id: str,
) -> None:
    """Test the power limits are unavailable unless both are known."""
    mock_zonneplan_client.async_get_battery_home_optimization.return_value = (
        BatteryHomeOptimization(max_desired_charge_power_watts=2000)
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_charge", "expected_discharge"),
    [
        pytest.param(MAX_CHARGE_POWER_ENTITY_ID, 1500, 1500, 800, id="charge"),
        pytest.param(MAX_DISCHARGE_POWER_ENTITY_ID, 500, 2500, 500, id="discharge"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_power_limit(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    entity_id: str,
    value: int,
    expected_charge: int,
    expected_discharge: int,
) -> None:
    """Test setting a power limit sends both limits and refreshes."""
    assert mock_zonneplan_client.async_get_battery_home_optimization.call_count == 1

    await _set_value(hass, entity_id, value)

    mock_zonneplan_client.async_enable_battery_home_optimization.assert_awaited_once_with(
        CONNECTION_UUID,
        CONTRACT_UUID,
        max_charge_power_w=expected_charge,
        max_discharge_power_w=expected_discharge,
    )
    assert mock_zonneplan_client.async_get_battery_home_optimization.call_count == 2


@pytest.mark.usefixtures("init_integration")
async def test_set_power_limits_in_a_row(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test quick successive power limit writes keep each other's limit."""

    async def _enable(
        connection_uuid: str,
        contract_uuid: str,
        *,
        max_charge_power_w: int,
        max_discharge_power_w: int,
    ) -> None:
        mock_zonneplan_client.async_get_battery_home_optimization.return_value = (
            replace(
                mock_zonneplan_client.async_get_battery_home_optimization.return_value,
                max_desired_charge_power_watts=max_charge_power_w,
                max_desired_discharge_power_watts=max_discharge_power_w,
            )
        )

    mock_zonneplan_client.async_enable_battery_home_optimization.side_effect = _enable

    await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1500)
    await _set_value(hass, MAX_DISCHARGE_POWER_ENTITY_ID, 500)
    await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1200)

    assert (
        mock_zonneplan_client.async_enable_battery_home_optimization.await_args_list
        == [
            call(
                CONNECTION_UUID,
                CONTRACT_UUID,
                max_charge_power_w=1500,
                max_discharge_power_w=800,
            ),
            call(
                CONNECTION_UUID,
                CONTRACT_UUID,
                max_charge_power_w=1500,
                max_discharge_power_w=500,
            ),
            call(
                CONNECTION_UUID,
                CONTRACT_UUID,
                max_charge_power_w=1200,
                max_discharge_power_w=500,
            ),
        ]
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_power_limit_mode_changed_in_app(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test a mode change since the last poll blocks writing the power limits."""
    mock_zonneplan_client.async_get_battery_control_mode.return_value = _control_mode(
        BatteryMode.SELF_CONSUMPTION, available=True
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1500)

    assert exc_info.value.translation_key == "home_optimization_not_active"
    mock_zonneplan_client.async_enable_battery_home_optimization.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_power_limit_control_mode_error(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the power limits are not written when the control mode can't be fetched."""
    mock_zonneplan_client.async_get_battery_control_mode.side_effect = (
        ZonneplanConnectionError("boom")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1500)

    assert exc_info.value.translation_key == "cannot_connect"
    mock_zonneplan_client.async_enable_battery_home_optimization.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_price_spread_wrong_mode(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the price spread can't be set outside day-ahead arbitrage."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await _set_value(hass, PRICE_SPREAD_ENTITY_ID, 0.1)

    assert exc_info.value.translation_key == "day_ahead_arbitrage_not_active"
    mock_zonneplan_client.async_enable_battery_day_ahead_arbitrage.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("control_mode", [BatteryMode.DAY_AHEAD_ARBITRAGE])
async def test_set_power_limit_wrong_mode(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the power limits can't be set outside home optimization."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1500)

    assert exc_info.value.translation_key == "home_optimization_not_active"
    mock_zonneplan_client.async_enable_battery_home_optimization.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("control_mode", [BatteryMode.DAY_AHEAD_ARBITRAGE])
async def test_set_price_spread(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test setting the price spread keeps the market time resolution."""
    assert mock_zonneplan_client.async_get_battery_day_ahead_arbitrage.call_count == 1

    await _set_value(hass, PRICE_SPREAD_ENTITY_ID, 0.12)

    mock_zonneplan_client.async_enable_battery_day_ahead_arbitrage.assert_awaited_once_with(
        CONTRACT_UUID,
        price_spread=0.12,
        market_time_resolution=MarketTimeResolution.QUARTER_HOUR,
    )
    assert mock_zonneplan_client.async_get_battery_day_ahead_arbitrage.call_count == 2


@pytest.mark.parametrize("control_mode", [BatteryMode.DAY_AHEAD_ARBITRAGE])
async def test_set_price_spread_not_set_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the price spread can't be set before day-ahead arbitrage was set up."""
    mock_zonneplan_client.async_get_battery_day_ahead_arbitrage.return_value = (
        BatteryDayAheadArbitrage()
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(PRICE_SPREAD_ENTITY_ID))
    assert state.state == "unknown"

    with pytest.raises(ServiceValidationError) as exc_info:
        await _set_value(hass, PRICE_SPREAD_ENTITY_ID, 0.1)

    assert exc_info.value.translation_key == "day_ahead_arbitrage_not_set_up"
    mock_zonneplan_client.async_enable_battery_day_ahead_arbitrage.assert_not_awaited()


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_set_backup_reserve(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test setting the backup reserve in any mode refreshes the battery."""
    assert mock_zonneplan_client.async_get_battery.call_count == 1

    await _set_value(hass, BACKUP_RESERVE_ENTITY_ID, 2000)

    mock_zonneplan_client.async_set_battery_backup_reserve.assert_awaited_once_with(
        CONNECTION_UUID, CONTRACT_UUID, 2000
    )
    assert mock_zonneplan_client.async_get_battery.call_count == 2


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(
            ZonneplanTimeoutError("timed out"), "timeout_connect", id="timeout_error"
        ),
        pytest.param(
            ZonneplanConnectionError("boom"), "cannot_connect", id="connection_error"
        ),
        pytest.param(
            ZonneplanRateLimitError("slow down", retry_after=30),
            "rate_limited",
            id="rate_limit_error",
        ),
        pytest.param(ZonneplanRequestError("rejected"), "api_error", id="api_error"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_value_error(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test errors while setting a value."""
    mock_zonneplan_client.async_enable_battery_home_optimization.side_effect = exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1500)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key
    assert mock_zonneplan_client.async_get_battery_home_optimization.call_count == 1


async def test_set_value_authentication_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test an authentication error while setting a value starts a reauth flow."""
    mock_zonneplan_client.async_enable_battery_home_optimization.side_effect = (
        ZonneplanAuthenticationError("bad token")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _set_value(hass, MAX_CHARGE_POWER_ENTITY_ID, 1500)
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "invalid_auth"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id


@pytest.mark.usefixtures("init_integration")
async def test_number_update(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the settings refresh with the control mode and are unavailable on errors."""
    assert (state := hass.states.get(MAX_CHARGE_POWER_ENTITY_ID))
    assert state.state == "2500"

    mock_zonneplan_client.async_get_battery_home_optimization.side_effect = (
        ZonneplanConnectionError("boom")
    )
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(MAX_CHARGE_POWER_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    mock_zonneplan_client.async_get_battery_home_optimization.side_effect = None
    mock_zonneplan_client.async_get_battery_home_optimization.return_value.max_desired_charge_power_watts = 1200
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(MAX_CHARGE_POWER_ENTITY_ID))
    assert state.state == "1200"


@pytest.mark.usefixtures("init_integration")
async def test_number_control_mode_update_failed(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the settings are unavailable while the control mode can't be fetched."""
    mock_zonneplan_client.async_get_battery_control_mode.side_effect = (
        ZonneplanConnectionError("boom")
    )
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in (
        MAX_CHARGE_POWER_ENTITY_ID,
        MAX_DISCHARGE_POWER_ENTITY_ID,
        PRICE_SPREAD_ENTITY_ID,
    ):
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNAVAILABLE

    mock_zonneplan_client.async_get_battery_control_mode.side_effect = None
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(MAX_CHARGE_POWER_ENTITY_ID))
    assert state.state == "2500"


async def test_number_control_mode_unavailable_at_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the settings numbers are added once the control mode is known."""
    mock_zonneplan_client.async_get_battery_control_mode.side_effect = (
        ZonneplanConnectionError("boom")
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(MAX_CHARGE_POWER_ENTITY_ID) is None
    assert hass.states.get(PRICE_SPREAD_ENTITY_ID) is None

    mock_zonneplan_client.async_get_battery_control_mode.side_effect = None
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(MAX_CHARGE_POWER_ENTITY_ID))
    assert state.state == "2500"
    assert hass.states.get(PRICE_SPREAD_ENTITY_ID)


@pytest.mark.usefixtures("init_integration")
async def test_number_mode_no_longer_available(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the numbers become unavailable when the battery drops their mode."""
    mock_zonneplan_client.async_get_battery_control_mode.return_value = _control_mode(
        BatteryMode.SELF_CONSUMPTION, available=False
    )
    freezer.tick(BATTERY_CONTROL_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in (
        MAX_CHARGE_POWER_ENTITY_ID,
        MAX_DISCHARGE_POWER_ENTITY_ID,
        PRICE_SPREAD_ENTITY_ID,
    ):
        assert (state := hass.states.get(entity_id))
        assert state.state == STATE_UNAVAILABLE
