"""Tests for the Intesis Modbus button platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, WriteEvent
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import INIT_VALUE

PREFIX = "button.inmbsmhi001r000_air_conditioner_"
CLEAR = PREFIX + "clear_external_temperature_reference"
RESET = PREFIX + "reset_error"
RESTART_GATEWAY = "button.inmbsmhi001r000_restart"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_get_unit")
async def test_all_buttons_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Every button matches its snapshot."""
    with patch("homeassistant.components.intesis_modbus.PLATFORMS", [Platform.BUTTON]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "address", "value"),
    [
        pytest.param(CLEAR, 22, INIT_VALUE, id="clear_external_temperature"),
        pytest.param(RESET, 45, 1, id="reset_error"),
        pytest.param(RESTART_GATEWAY, 99, 1, id="restart_gateway"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_button_writes_its_register(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    address: int,
    value: int,
) -> None:
    """Each button sends its command to the gateway."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(address, value)]


@pytest.mark.parametrize(
    ("entity_id", "address", "error"),
    [
        pytest.param(RESET, 45, ModbusTimeoutError(), id="reset_error_unanswered"),
        pytest.param(
            RESTART_GATEWAY, 99, IllegalDataAddressError(), id="restart_gateway_refused"
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_press_failure_raises_home_assistant_error(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    entity_id: str,
    address: int,
    error: Exception,
) -> None:
    """A command the gateway does not take surfaces as an error."""
    mock_connection.for_unit(1).fail_write(address, error)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "write_failed"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_restart_gateway_accepts_an_unanswered_write(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """The gateway restarts without answering the request, which is not a failure."""
    mock_connection.for_unit(1).fail_write(99, ModbusTimeoutError())
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: RESTART_GATEWAY},
        blocking=True,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_buttons_stay_when_a_register_block_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """A command reads nothing, so a block that stops answering does not hide it."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(21, IllegalDataAddressError())
    unit.fail_read(60, IllegalDataAddressError())
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for entity_id in (CLEAR, RESET, RESTART_GATEWAY):
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_unreachable_air_conditioner_takes_only_its_own_buttons(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The gateway can still be restarted when it cannot reach the air conditioner."""
    mock_connection.for_unit(1).holding[11] = 65535
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CLEAR).state == STATE_UNAVAILABLE
    assert hass.states.get(RESET).state == STATE_UNAVAILABLE
    assert hass.states.get(RESTART_GATEWAY).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_restart_gateway_is_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Restarting the gateway has to be enabled by hand."""
    assert hass.states.get(RESTART_GATEWAY) is None
    entry = entity_registry.async_get(RESTART_GATEWAY)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
