"""Tests for the Sofar integration services."""

from collections.abc import Callable
from unittest.mock import patch

from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit, WriteEvent
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from sofar_modbus import BatteryConfigCellType, BatteryConfigWriteStatus

from homeassistant.components.sofar.const import DOMAIN
from homeassistant.components.sofar.services import SofarService, SofarServiceArgument
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import (
    MOCK_ENTRY_DATA,
    MOCK_HYBRID_MODEL,
    MOCK_HYBRID_SERIAL,
    deny_charge_cutoff,
    seed_hybrid_inverter,
)

FEED_IN_MODE_REGISTER = 0x1023
FEED_IN_POWER_REGISTER = 0x1024
POWER_CONTROL_REGISTER = 0x1105
ACTIVE_POWER_LIMIT_REGISTER = 0x1106
PASSIVE_TIMEOUT_REGISTER = 0x1184
PASSIVE_TIMEOUT_ACTION_REGISTER = 0x1185
PASSIVE_GRID_POWER_REGISTER = 0x1187
PASSIVE_BATTERY_POWER_MIN_REGISTER = 0x1189
PASSIVE_BATTERY_POWER_MAX_REGISTER = 0x118B
DEPTH_OF_DISCHARGE_REGISTER = 0x104D
END_OF_DISCHARGE_REGISTER = 0x104E
CELL_TYPE_REGISTER = 0x1051
EPS_BUFFER_REGISTER = 0x1052
BATTERY_CONFIG_STATUS_REGISTER = 0x1053
CHARGE_CUTOFF_REGISTER = 0x105B

DISCHARGE_CUTOFFS = {
    SofarServiceArgument.ON_GRID_DISCHARGE_CUTOFF_SOC: 30,
    SofarServiceArgument.OFF_GRID_DISCHARGE_CUTOFF_SOC: 10,
    SofarServiceArgument.OFF_GRID_RECOVERY_SOC: 15,
}


async def _setup_hybrid(
    hass: HomeAssistant, *seeds: Callable[[MockModbusUnit], None]
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up a hybrid inverter, which serves the passive-mode registers."""
    connection = MockModbusConnection()
    for seed in (seed_hybrid_inverter, *seeds):
        seed(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_ENTRY_DATA,
        title=MOCK_HYBRID_MODEL,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.sofar.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry, connection


async def test_set_feed_in_limit(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test the feed-in limit reaches both registers as one write."""
    await hass.services.async_call(
        DOMAIN,
        SofarService.SET_FEED_IN_LIMIT,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: init_integration.entry_id,
            SofarServiceArgument.MODE: "enabled_feed_in_limitation",
            SofarServiceArgument.MAX_POWER: 3000,
        },
        blocking=True,
    )

    holding = mock_connection.for_unit(1).holding
    assert holding[FEED_IN_MODE_REGISTER] == 1
    # The register counts in 100 W steps.
    assert holding[FEED_IN_POWER_REGISTER] == 30


async def test_set_active_power_limit(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test the active power limit arms its flag and writes the percentage."""
    await hass.services.async_call(
        DOMAIN,
        SofarService.SET_ACTIVE_POWER_LIMIT,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: init_integration.entry_id,
            SofarServiceArgument.ENABLED: True,
            SofarServiceArgument.LIMIT: 42.5,
        },
        blocking=True,
    )

    holding = mock_connection.for_unit(1).holding
    assert holding[POWER_CONTROL_REGISTER] == 1
    # The register counts in 0.1% steps.
    assert holding[ACTIVE_POWER_LIMIT_REGISTER] == 425


async def test_set_passive_mode_timeout(hass: HomeAssistant) -> None:
    """Test the passive-mode timeout and its action go out together."""
    entry, connection = await _setup_hybrid(hass)

    await hass.services.async_call(
        DOMAIN,
        SofarService.SET_PASSIVE_MODE_TIMEOUT,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: entry.entry_id,
            SofarServiceArgument.TIMEOUT: 300,
            SofarServiceArgument.ACTION: "return_to_previous_mode",
        },
        blocking=True,
    )

    holding = connection.for_unit(1).holding
    assert holding[PASSIVE_TIMEOUT_REGISTER] == 300
    assert holding[PASSIVE_TIMEOUT_ACTION_REGISTER] == 1


async def test_set_passive_mode_power(hass: HomeAssistant) -> None:
    """Test the three passive-mode setpoints go out as one block."""
    entry, connection = await _setup_hybrid(hass)

    await hass.services.async_call(
        DOMAIN,
        SofarService.SET_PASSIVE_MODE_POWER,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: entry.entry_id,
            SofarServiceArgument.GRID_POWER: 1000,
            SofarServiceArgument.BATTERY_POWER_MIN: -2000,
            SofarServiceArgument.BATTERY_POWER_MAX: 2000,
        },
        blocking=True,
    )

    holding = connection.for_unit(1).holding
    # Each setpoint is a signed 32-bit value over two registers.
    assert holding[PASSIVE_GRID_POWER_REGISTER] == 0
    assert holding[PASSIVE_GRID_POWER_REGISTER + 1] == 1000
    assert holding[PASSIVE_BATTERY_POWER_MIN_REGISTER] == 0xFFFF
    assert holding[PASSIVE_BATTERY_POWER_MIN_REGISTER + 1] == 63536
    assert holding[PASSIVE_BATTERY_POWER_MAX_REGISTER] == 0
    assert holding[PASSIVE_BATTERY_POWER_MAX_REGISTER + 1] == 2000


def _commit_battery_config(unit: MockModbusUnit) -> None:
    """Make a lithium battery's config writes commit at once."""
    unit.holding[CELL_TYPE_REGISTER] = BatteryConfigCellType.LITHIUM_IRON_PHOSPHATE
    unit.on_write(
        lambda _: unit.holding.__setitem__(
            BATTERY_CONFIG_STATUS_REGISTER, BatteryConfigWriteStatus.SUCCESS
        )
    )


@pytest.mark.parametrize(
    ("data", "charge_cutoff"),
    [
        pytest.param({}, 95, id="discharge_only"),
        pytest.param(
            {SofarServiceArgument.CHARGE_CUTOFF_SOC: 90}, 90, id="with_charge_cutoff"
        ),
    ],
)
async def test_set_battery_cutoffs(
    hass: HomeAssistant, data: dict[str, int], charge_cutoff: int
) -> None:
    """Test the app's cut-offs reach the battery config registers."""
    entry, connection = await _setup_hybrid(hass, _commit_battery_config)

    await hass.services.async_call(
        DOMAIN,
        SofarService.SET_BATTERY_CUTOFFS,
        {
            CommonServiceArgument.CONFIG_ENTRY_ID: entry.entry_id,
            **DISCHARGE_CUTOFFS,
            **data,
        },
        blocking=True,
    )

    # The inverter stores each cut-off as its distance from 100% or 0%.
    assert [
        connection.for_unit(1).holding[address]
        for address in (
            DEPTH_OF_DISCHARGE_REGISTER,
            END_OF_DISCHARGE_REGISTER,
            EPS_BUFFER_REGISTER,
            CHARGE_CUTOFF_REGISTER,
        )
    ] == [70, 90, 5, charge_cutoff]


async def test_charge_cutoff_rejected_when_not_served(hass: HomeAssistant) -> None:
    """Test a charge cut-off is refused when the mask leaves out 0x105B."""
    entry, connection = await _setup_hybrid(
        hass, deny_charge_cutoff, _commit_battery_config
    )
    writes: list[WriteEvent] = []
    connection.for_unit(1).on_write(writes.append)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SofarService.SET_BATTERY_CUTOFFS,
            {
                CommonServiceArgument.CONFIG_ENTRY_ID: entry.entry_id,
                **DISCHARGE_CUTOFFS,
                SofarServiceArgument.CHARGE_CUTOFF_SOC: 90,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "charge_cutoff_unsupported"
    assert writes == []


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (
            SofarService.SET_PASSIVE_MODE_TIMEOUT,
            {
                SofarServiceArgument.TIMEOUT: 60,
                SofarServiceArgument.ACTION: "force_standby",
            },
        ),
        (
            SofarService.SET_PASSIVE_MODE_POWER,
            {
                SofarServiceArgument.GRID_POWER: 0,
                SofarServiceArgument.BATTERY_POWER_MIN: 0,
                SofarServiceArgument.BATTERY_POWER_MAX: 0,
            },
        ),
        (SofarService.SET_BATTERY_CUTOFFS, DISCHARGE_CUTOFFS),
    ],
)
async def test_action_rejected_when_unsupported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
    data: dict[str, int | str],
) -> None:
    """Test a battery action is refused by a PV-only inverter."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CommonServiceArgument.CONFIG_ENTRY_ID: init_integration.entry_id, **data},
            blocking=True,
        )


@pytest.mark.parametrize(
    "max_power",
    [pytest.param(3050, id="int"), pytest.param(3000.9, id="fractional")],
)
async def test_max_power_not_a_multiple_of_100_is_a_service_error(
    hass: HomeAssistant, init_integration: MockConfigEntry, max_power: float
) -> None:
    """Test a non-multiple-of-100 max_power is rejected before writing."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SofarService.SET_FEED_IN_LIMIT,
            {
                CommonServiceArgument.CONFIG_ENTRY_ID: init_integration.entry_id,
                SofarServiceArgument.MODE: "disabled",
                SofarServiceArgument.MAX_POWER: max_power,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "max_power_not_a_multiple_of_100"


async def test_unexpected_value_error_is_a_service_error(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a library ValueError the handlers don't preempt still translates."""
    device = init_integration.runtime_data.readings.device
    with (
        patch.object(
            device.feed_in, "async_write_limit", side_effect=ValueError("boom")
        ),
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SofarService.SET_FEED_IN_LIMIT,
            {
                CommonServiceArgument.CONFIG_ENTRY_ID: init_integration.entry_id,
                SofarServiceArgument.MODE: "disabled",
                SofarServiceArgument.MAX_POWER: 3000,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_action_value"


async def test_write_failure_is_a_home_assistant_error(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a ModbusError surfaces as a HomeAssistantError."""
    mock_connection.for_unit(1).fail_write(FEED_IN_MODE_REGISTER, ModbusError("busy"))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SofarService.SET_FEED_IN_LIMIT,
            {
                CommonServiceArgument.CONFIG_ENTRY_ID: init_integration.entry_id,
                SofarServiceArgument.MODE: "disabled",
                SofarServiceArgument.MAX_POWER: 0,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            SofarService.SET_FEED_IN_LIMIT,
            {
                SofarServiceArgument.MODE: "disabled",
                SofarServiceArgument.MAX_POWER: 10_000_000,
            },
            id="feed_in_max_power",
        ),
        pytest.param(
            SofarService.SET_PASSIVE_MODE_TIMEOUT,
            {
                SofarServiceArgument.TIMEOUT: 70000,
                SofarServiceArgument.ACTION: "force_standby",
            },
            id="passive_timeout",
        ),
        pytest.param(
            SofarService.SET_PASSIVE_MODE_POWER,
            {
                SofarServiceArgument.GRID_POWER: 200_000,
                SofarServiceArgument.BATTERY_POWER_MIN: 0,
                SofarServiceArgument.BATTERY_POWER_MAX: 0,
            },
            id="passive_grid_power",
        ),
        pytest.param(
            SofarService.SET_BATTERY_CUTOFFS,
            {
                **DISCHARGE_CUTOFFS,
                SofarServiceArgument.ON_GRID_DISCHARGE_CUTOFF_SOC: 101,
            },
            id="on_grid_discharge_cutoff",
        ),
        pytest.param(
            SofarService.SET_BATTERY_CUTOFFS,
            {
                **DISCHARGE_CUTOFFS,
                SofarServiceArgument.OFF_GRID_DISCHARGE_CUTOFF_SOC: 31,
            },
            id="off_grid_discharge_cutoff",
        ),
        pytest.param(
            SofarService.SET_BATTERY_CUTOFFS,
            {**DISCHARGE_CUTOFFS, SofarServiceArgument.OFF_GRID_RECOVERY_SOC: 14},
            id="off_grid_recovery",
        ),
        pytest.param(
            SofarService.SET_BATTERY_CUTOFFS,
            {**DISCHARGE_CUTOFFS, SofarServiceArgument.CHARGE_CUTOFF_SOC: 59},
            id="charge_cutoff",
        ),
    ],
)
async def test_value_past_the_selector_bounds_is_refused(
    hass: HomeAssistant,
    service: str,
    data: dict[str, int | str],
) -> None:
    """Test the schema bounds a scripted call, which skips the selectors."""
    entry, _ = await _setup_hybrid(hass)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            service,
            {CommonServiceArgument.CONFIG_ENTRY_ID: entry.entry_id, **data},
            blocking=True,
        )
