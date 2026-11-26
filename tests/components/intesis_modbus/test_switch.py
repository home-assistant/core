"""Tests for the Intesis Modbus switch platform."""

from unittest.mock import MagicMock, patch

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

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

GATEWAY = "switch.inmbsmhi001r000_"
UNIT = "switch.inmbsmhi001r000_air_conditioner_"
DISABLED = GATEWAY + "gateway_disabled"
MASTER = GATEWAY + "xy_bus_master"
LOCK = UNIT + "remote_controller_lock"
WINDOW = UNIT + "window_contact"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_switches_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Every switch matches its snapshot."""
    with patch("homeassistant.components.intesis_modbus.PLATFORMS", [Platform.SWITCH]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "address"),
    [
        pytest.param(DISABLED, 7, id="gateway_disabled"),
        pytest.param(MASTER, 98, id="xy_bus_master"),
        pytest.param(LOCK, 8, id="remote_controller_lock"),
        pytest.param(WINDOW, 6, id="window_contact"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_switch_writes_its_register_and_reads_it_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    entity_id: str,
    address: int,
) -> None:
    """Each switch writes its own register and follows what the gateway reads."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(address, 1), (address, 0)]
    # A second refresh this soon is held back, so the next poll shows it
    await _poll(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize("entity_id", [DISABLED, MASTER])
@pytest.mark.usefixtures("init_integration")
async def test_gateway_switches_are_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """The settings that change how the gateway works have to be enabled by hand."""
    assert hass.states.get(entity_id) is None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("init_integration")
async def test_write_failure_raises_home_assistant_error(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """A write the gateway does not answer surfaces as an error."""
    mock_connection.for_unit(1).fail_write(8, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SwitchService.TURN_ON,
            {TargetKey.ENTITY_ID: LOCK},
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "write_failed"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_unreachable_air_conditioner_only_takes_its_own_switches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """What the gateway holds itself stays when it cannot reach the air conditioner."""
    mock_connection.for_unit(1).holding[11] = 65535
    await _poll(hass, freezer)
    assert hass.states.get(LOCK).state == STATE_UNAVAILABLE
    for entity_id in (DISABLED, MASTER, WINDOW):
        assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    ("address", "lost", "kept"),
    [
        pytest.param(0, (DISABLED, LOCK, WINDOW), (MASTER,), id="control"),
        pytest.param(97, (MASTER,), (DISABLED, LOCK, WINDOW), id="diagnostics"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_failed_block_only_takes_its_own_switches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    address: int,
    lost: tuple[str, ...],
    kept: tuple[str, ...],
) -> None:
    """Switches read from a block that stops answering go unavailable alone."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(address, IllegalDataAddressError())
    await _poll(hass, freezer)
    assert {hass.states.get(entity_id).state for entity_id in lost} == {
        STATE_UNAVAILABLE
    }
    assert {hass.states.get(entity_id).state for entity_id in kept} == {STATE_OFF}
    unit.fail_read(address, None)
    await _poll(hass, freezer)
    assert {hass.states.get(entity_id).state for entity_id in lost} == {STATE_OFF}
