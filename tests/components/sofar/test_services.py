"""Test the Sofar Inverter Modbus services."""

from unittest.mock import patch

from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.sofar.const import DOMAIN
from homeassistant.components.sofar.services import (
    ATTR_ACTION,
    ATTR_BATTERY_POWER_MAX,
    ATTR_BATTERY_POWER_MIN,
    ATTR_ENABLED,
    ATTR_GRID_POWER,
    ATTR_LIMIT,
    ATTR_MAX_POWER,
    ATTR_TIMEOUT,
    SERVICE_SET_ACTIVE_POWER_LIMIT,
    SERVICE_SET_FEED_IN_LIMIT,
    SERVICE_SET_PASSIVE_MODE_POWER,
    SERVICE_SET_PASSIVE_MODE_TIMEOUT,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import (
    MOCK_HYBRID_MODEL,
    MOCK_HYBRID_SERIAL,
    MOCK_USER_INPUT,
    seed_hybrid_inverter,
)

from tests.common import MockConfigEntry

FEED_IN_MODE_REGISTER = 0x1023
FEED_IN_POWER_REGISTER = 0x1024
POWER_CONTROL_REGISTER = 0x1105
ACTIVE_POWER_LIMIT_REGISTER = 0x1106
PASSIVE_TIMEOUT_REGISTER = 0x1184
PASSIVE_TIMEOUT_ACTION_REGISTER = 0x1185
PASSIVE_GRID_POWER_REGISTER = 0x1187
PASSIVE_BATTERY_POWER_MIN_REGISTER = 0x1189
PASSIVE_BATTERY_POWER_MAX_REGISTER = 0x118B


async def _setup_hybrid(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MockModbusConnection]:
    """Set up a hybrid inverter, which serves the passive-mode registers."""
    connection = MockModbusConnection()
    seed_hybrid_inverter(connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_HYBRID_SERIAL,
        data=MOCK_USER_INPUT,
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
        SERVICE_SET_FEED_IN_LIMIT,
        {
            ATTR_CONFIG_ENTRY_ID: init_integration.entry_id,
            ATTR_MODE: "enabled_feed_in_limitation",
            ATTR_MAX_POWER: 3000,
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
        SERVICE_SET_ACTIVE_POWER_LIMIT,
        {
            ATTR_CONFIG_ENTRY_ID: init_integration.entry_id,
            ATTR_ENABLED: True,
            ATTR_LIMIT: 42.5,
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
        SERVICE_SET_PASSIVE_MODE_TIMEOUT,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_TIMEOUT: 300,
            ATTR_ACTION: "return_to_previous_mode",
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
        SERVICE_SET_PASSIVE_MODE_POWER,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_GRID_POWER: 1000,
            ATTR_BATTERY_POWER_MIN: -2000,
            ATTR_BATTERY_POWER_MAX: 2000,
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


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (
            SERVICE_SET_PASSIVE_MODE_TIMEOUT,
            {ATTR_TIMEOUT: 60, ATTR_ACTION: "force_standby"},
        ),
        (
            SERVICE_SET_PASSIVE_MODE_POWER,
            {
                ATTR_GRID_POWER: 0,
                ATTR_BATTERY_POWER_MIN: 0,
                ATTR_BATTERY_POWER_MAX: 0,
            },
        ),
    ],
)
async def test_action_rejected_when_unsupported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
    data: dict[str, int | str],
) -> None:
    """Test a passive-mode action is refused by a PV-only inverter."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: init_integration.entry_id, **data},
            blocking=True,
        )


async def test_invalid_action_value_is_a_service_error(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the library's ValueError surfaces as a ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FEED_IN_LIMIT,
            {
                ATTR_CONFIG_ENTRY_ID: init_integration.entry_id,
                ATTR_MODE: "disabled",
                ATTR_MAX_POWER: 3050,
            },
            blocking=True,
        )


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
            SERVICE_SET_FEED_IN_LIMIT,
            {
                ATTR_CONFIG_ENTRY_ID: init_integration.entry_id,
                ATTR_MODE: "disabled",
                ATTR_MAX_POWER: 0,
            },
            blocking=True,
        )
