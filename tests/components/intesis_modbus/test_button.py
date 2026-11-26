"""Tests for the Intesis Modbus button platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, WriteEvent
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import INIT_VALUE

PREFIX = "button.inmbsmhi001r000_air_conditioner_"
CLEAR = PREFIX + "clear_external_temperature_reference"
RESET = PREFIX + "reset_error"
RESET_GATEWAY = "button.inmbsmhi001r000_reset_gateway"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_buttons_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
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
        pytest.param(RESET_GATEWAY, 99, 1, id="reset_gateway"),
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
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert [(w.address, w.values[0]) for w in writes] == [(address, value)]


@pytest.mark.usefixtures("init_integration")
async def test_press_failure_raises_home_assistant_error(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """A command the gateway does not answer surfaces as an error."""
    mock_connection.for_unit(1).fail_write(45, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: RESET}, blocking=True
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "write_failed"


@pytest.mark.usefixtures("init_integration")
async def test_unreachable_air_conditioner_takes_its_buttons(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The buttons go unavailable with the air conditioner."""
    mock_connection.for_unit(1).holding[11] = 65535
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(CLEAR).state == STATE_UNAVAILABLE
    assert hass.states.get(RESET).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_reset_gateway_is_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Resetting the gateway has to be enabled by hand."""
    assert hass.states.get(RESET_GATEWAY) is None
    entry = entity_registry.async_get(RESET_GATEWAY)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_reset_gateway_does_not_wait_for_an_answer(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """The gateway restarts without answering, which is not a failure."""
    mock_connection.for_unit(1).fail_write(99, ModbusTimeoutError())
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: RESET_GATEWAY}, blocking=True
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_reset_gateway_stays_when_the_air_conditioner_is_unreachable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The gateway can still be reset when it cannot reach the air conditioner."""
    mock_connection.for_unit(1).holding[11] = 65535
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(RESET).state == STATE_UNAVAILABLE
    assert hass.states.get(RESET_GATEWAY).state != STATE_UNAVAILABLE
