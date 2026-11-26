"""Tests for the Intesis Modbus number platform."""

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

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntityCapabilityAttribute,
    NumberService,
    NumberServiceArgument,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

EXTERNAL = "number.inmbsmhi001r000_air_conditioner_external_temperature_reference"
TIMEOUT = "number.inmbsmhi001r000_air_conditioner_open_window_timeout"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_numbers_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Every number matches its snapshot."""
    with patch("homeassistant.components.intesis_modbus.PLATFORMS", [Platform.NUMBER]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_external_temperature_is_written_in_the_gateway_format(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """The external reference lands on register 22 and is read back."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {TargetKey.ENTITY_ID: EXTERNAL, NumberServiceArgument.VALUE: 21.5},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [(w.address, w.values[0]) for w in writes] == [(22, 215)]
    assert hass.states.get(EXTERNAL).state == "21.5"


@pytest.mark.usefixtures("init_integration")
async def test_external_temperature_follows_the_temperature_format(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway switched to whole degrees is written and read in whole degrees."""
    unit = mock_connection.for_unit(1)
    for address, value in {4: 22, 5: 20, 23: 22, 24: 30, 25: 16}.items():
        unit.holding[address] = value
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        hass.states.get(EXTERNAL).attributes[NumberEntityCapabilityAttribute.STEP] == 1
    )
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {TargetKey.ENTITY_ID: EXTERNAL, NumberServiceArgument.VALUE: 22},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [(w.address, w.values[0]) for w in writes] == [(22, 22)]
    assert hass.states.get(EXTERNAL).state == "22.0"


@pytest.mark.usefixtures("init_integration")
async def test_open_window_timeout_is_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The open window timeout has to be enabled by hand."""
    assert hass.states.get(TIMEOUT) is None
    entry = entity_registry.async_get(TIMEOUT)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("value", "written"),
    [
        pytest.param(5, 5, id="whole_minutes"),
        pytest.param(4.6, 5, id="rounded_to_the_nearest_minute"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_open_window_timeout_is_written_in_whole_minutes(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    value: float,
    written: int,
) -> None:
    """The timeout lands on register 13 as the nearest whole minute."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {TargetKey.ENTITY_ID: TIMEOUT, NumberServiceArgument.VALUE: value},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(13, written)]


@pytest.mark.usefixtures("init_integration")
async def test_write_failure_raises_home_assistant_error(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """A write the gateway does not answer surfaces as an error."""
    mock_connection.for_unit(1).fail_write(22, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            NumberService.SET_VALUE,
            {TargetKey.ENTITY_ID: EXTERNAL, NumberServiceArgument.VALUE: 20},
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "write_failed"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_unreachable_air_conditioner_takes_its_numbers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """The numbers go unavailable with the air conditioner."""
    mock_connection.for_unit(1).holding[11] = 65535
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(EXTERNAL).state == STATE_UNAVAILABLE
    assert hass.states.get(TIMEOUT).state == STATE_UNAVAILABLE
