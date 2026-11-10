"""Tests for the Intesis Modbus climate platform."""

from datetime import timedelta
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

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.intesis_modbus.const import CONF_HAS_VANE, DOMAIN
from homeassistant.components.intesis_modbus.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import MOCK_ENTRY_DATA, seed_initialising_single_unit

ENTITY_ID = "climate.inmbsmhi001r000"


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_climate_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """The climate entity matches its snapshot."""
    with patch("homeassistant.components.intesis_modbus.PLATFORMS", [Platform.CLIMATE]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fan_mode_powerful_not_offered_on_three_speed_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A unit with three speeds does not list powerful."""
    mock_connection.for_unit(1).holding[21] = 3
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_FAN_MODES] == ["auto", "low", "medium", "high"]


async def test_set_unsupported_fan_mode_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """Asking a three-speed unit for powerful is refused before any write."""
    unit = mock_connection.for_unit(1)
    unit.holding[21] = 3
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "powerful"},
            blocking=True,
        )
    assert writes == []


async def test_set_hvac_mode_cool_turns_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """Picking a mode on a unit that is off sets the mode, then turns it on."""
    unit = mock_connection.for_unit(1)
    unit.holding[0] = 0
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(1, 4), (0, 1)]
    assert hass.states.get(ENTITY_ID).state == HVACMode.COOL


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Off writes the power register only."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(0, 0)]
    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF


async def test_set_hvac_mode_heat_while_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A mode change always writes power on, as the cached power can be stale."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.DRY},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(1, 2), (0, 1)]


async def test_set_temperature_fan_swing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Temperature, fan and swing land on registers 4, 2 and 3."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 24.5},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "position_2"},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(4, 245), (2, 3), (3, 2)]
    await _poll(hass, freezer)  # the refresh after a write is debounced
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 24.5
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_SWING_MODE] == "position_2"


async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A temperature sent together with a mode applies both on a unit that is off."""
    unit = mock_connection.for_unit(1)
    unit.holding[0] = 0
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 22,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(1, 4), (0, 1), (4, 220)]
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 22


async def test_set_temperature_with_unsupported_hvac_mode_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A mode the unit does not have is refused before any write."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 22,
                ATTR_HVAC_MODE: HVACMode.AUTO,
            },
            blocking=True,
        )
    assert err.value.translation_key == "not_valid_hvac_mode"
    assert writes == []


async def test_set_hvac_mode_heat_cool(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Heat/cool selects the automatic mode of the unit."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    assert [(w.address, w.values[0]) for w in writes] == [(1, 0), (0, 1)]
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT_COOL


async def test_set_temperature_out_of_range_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A setpoint above the unit's maximum is refused."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 31},
            blocking=True,
        )


async def test_write_failure_raises_home_assistant_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A write the gateway does not answer surfaces as an error."""
    mock_connection.for_unit(1).fail_write(4, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22},
            blocking=True,
        )
    assert not isinstance(err.value, ServiceValidationError)
    assert err.value.translation_key == "write_failed"
    assert err.value.translation_placeholders is None


async def test_initialising_gateway_climate_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """While the gateway initialises the entity is unknown, not 3276.8 °C."""
    seed_initialising_single_unit(mock_connection.for_unit(1))
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_MIN_TEMP] == 16
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_FAN_MODE] is None
    assert state.attributes[ATTR_SWING_MODE] is None


async def test_unknown_mode_while_on_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A running unit whose mode register holds no value yet has no state."""
    mock_connection.for_unit(1).holding[1] = 0x8000
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_timeout_marks_unavailable_then_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A silent gateway makes the entity unavailable; the next poll restores it."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert init_integration.state is ConfigEntryState.LOADED
    mock_connection.for_unit(1).fail_requests(None)
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT
    assert mock_get_unit.call_count == 1


async def test_other_subsystem_failing_keeps_climate_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A refused block the climate entity does not read leaves it available."""
    mock_connection.for_unit(1).fail_read(60, IllegalDataAddressError())
    await _poll(hass, freezer)
    coordinator = init_integration.runtime_data
    assert coordinator.last_update_success
    assert "temperatures" in coordinator.data.failed
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


async def test_control_subsystem_failing_makes_climate_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A refused control block hides the climate entity, others still answer."""
    mock_connection.for_unit(1).fail_read(0, IllegalDataAddressError())
    await _poll(hass, freezer)
    assert init_integration.runtime_data.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_subsystem_failure_and_recovery_are_logged_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """A failing block is logged when it fails and when it answers again."""
    unit = mock_connection.for_unit(1)
    unit.fail_read(0, IllegalDataAddressError())
    await _poll(hass, freezer)
    await _poll(hass, freezer)
    assert caplog.text.count("control failed to refresh") == 1
    assert "control is available again" not in caplog.text
    unit.fail_read(0, None)
    await _poll(hass, freezer)
    await _poll(hass, freezer)
    assert caplog.text.count("control is available again") == 1
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


async def test_every_subsystem_failing_is_an_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """When no block answers the entity goes unavailable."""
    unit = mock_connection.for_unit(1)
    for address in (0, 13, 21, 31, 46, 55, 60, 65, 81, 97):
        unit.fail_read(address, IllegalDataAddressError())
    await _poll(hass, freezer)
    assert not init_integration.runtime_data.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_turn_on_and_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """The turn on and turn off actions write the power register."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert [(w.address, w.values[0]) for w in writes] == [(0, 0), (0, 1)]


async def test_unit_without_vane_has_no_swing(
    hass: HomeAssistant,
    mock_get_unit: MagicMock,
) -> None:
    """An entry set up without a vane offers no swing mode at all."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTESTINTESISNOVANE000000",
        data={**MOCK_ENTRY_DATA, CONF_HAS_VANE: False},
        title="INMBSMHI001R000",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert ATTR_SWING_MODE not in state.attributes
    assert ATTR_SWING_MODES not in state.attributes
    assert (
        not state.attributes[ATTR_SUPPORTED_FEATURES] & ClimateEntityFeature.SWING_MODE
    )
    assert state.attributes[ATTR_FAN_MODE] == "medium"
