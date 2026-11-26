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
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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
    state = hass.states.get(EXTERNAL)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_MIN] == 10
    assert state.attributes[ATTR_MAX] == 38
    assert state.attributes[ATTR_STEP] == 0.5
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: EXTERNAL, ATTR_VALUE: 21.5},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert [(w.address, w.values[0]) for w in writes] == [(22, 215)]
    assert hass.states.get(EXTERNAL).state == "21.5"


@pytest.mark.usefixtures("init_integration")
async def test_open_window_timeout_is_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The open window timeout has to be enabled by hand."""
    assert hass.states.get(TIMEOUT) is None
    entry = entity_registry.async_get(TIMEOUT)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_open_window_timeout_write_and_range(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """The timeout writes register 13 and refuses more than 30 minutes."""
    assert hass.states.get(TIMEOUT).state == "30"
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TIMEOUT, ATTR_VALUE: 5},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(13, 5)]
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: TIMEOUT, ATTR_VALUE: 31},
            blocking=True,
        )
    assert err.value.translation_domain == NUMBER_DOMAIN
    assert err.value.translation_key == "out_of_range"


@pytest.mark.usefixtures("init_integration")
async def test_write_failure_raises_home_assistant_error(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """A write the gateway does not answer surfaces as an error."""
    mock_connection.for_unit(1).fail_write(22, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: EXTERNAL, ATTR_VALUE: 20},
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
