"""Tests for the Ceiling Fan Infrared fan platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.e27_fan_light import E27FanLightCode
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache,
    snapshot_platform,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ceiling_fan_infrared.fan import CeilingFanIrRestoreData
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def fan_only() -> Generator[None]:
    """Enable only the fan platform."""
    with patch(
        "homeassistant.components.ceiling_fan_infrared.PLATFORMS",
        [Platform.FAN],
    ):
        yield


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of the fan platform."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_state_is_unknown_before_the_first_command(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the assumed state is unknown until a command establishes it."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_UNKNOWN


_FAN_ACTIONS: list[tuple[str, dict[str, int], E27FanLightCode, str, int | None]] = [
    (SERVICE_TURN_ON, {}, E27FanLightCode.FAN_TOGGLE, STATE_ON, None),
    (
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 0},
        E27FanLightCode.FAN_TOGGLE,
        STATE_OFF,
        0,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 1},
        E27FanLightCode.FAN_LOW,
        STATE_ON,
        33,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 50},
        E27FanLightCode.FAN_MEDIUM,
        STATE_ON,
        66,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 100},
        E27FanLightCode.FAN_HIGH,
        STATE_ON,
        100,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 0},
        E27FanLightCode.FAN_TOGGLE,
        STATE_OFF,
        0,
    ),
    (SERVICE_TURN_OFF, {}, E27FanLightCode.FAN_TOGGLE, STATE_OFF, 0),
]


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "expected_code",
        "expected_state",
        "expected_percentage",
    ),
    _FAN_ACTIONS,
)
@pytest.mark.usefixtures("infrared_codes")
async def test_fan_actions(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
    service: str,
    service_data: dict[str, int],
    expected_code: E27FanLightCode,
    expected_state: str,
    expected_percentage: int | None,
) -> None:
    """Test fan actions send the expected code and update the state."""
    config_entry = MockConfigEntry(
        domain="ceiling_fan_infrared",
        title="Ceiling fan via Test IR emitter",
        entry_id="1234567890",
        data={"infrared_entity_id": "infrared.test_ir_emitter"},
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert entity_id is not None

    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get(ATTR_PERCENTAGE) == expected_percentage


@pytest.mark.usefixtures("infrared_codes")
async def test_fan_toggle_is_only_sent_when_the_state_changes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the toggle key is not sent again for an unchanged assumed state."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert entity_id is not None

    mock_infrared_emitter_entity.send_command_calls.clear()

    for _ in range(2):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert mock_infrared_emitter_entity.send_command_calls == [
        E27FanLightCode.FAN_TOGGLE
    ]

    for _ in range(2):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    assert mock_infrared_emitter_entity.send_command_calls == [
        E27FanLightCode.FAN_TOGGLE,
        E27FanLightCode.FAN_TOGGLE,
    ]

    # Setting the percentage to 0 turns the fan off, which is a no-op here.
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls == [
        E27FanLightCode.FAN_TOGGLE,
        E27FanLightCode.FAN_TOGGLE,
    ]


async def test_fan_unavailable_when_emitter_is(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the fan becomes unavailable when the infrared emitter is."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state != STATE_UNAVAILABLE

    hass.states.async_set(
        mock_infrared_emitter_entity.entity_id,
        STATE_UNAVAILABLE,
        force_update=True,
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(
        mock_infrared_emitter_entity.entity_id,
        STATE_ON,
        force_update=True,
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id)) is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("infrared_codes")
async def test_state_restored_after_a_reload_while_the_emitter_is_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the assumed state survives a reload while the emitter is unavailable.

    The entity state is unavailable whenever the emitter is, so restoring from
    it alone would lose the assumed state and the next turn_on would toggle an
    already running fan off.
    """
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert entity_id is not None

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PERCENTAGE: 66},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 66

    hass.states.async_set(
        mock_infrared_emitter_entity.entity_id,
        STATE_UNAVAILABLE,
        force_update=True,
    )
    await hass.async_block_till_done()
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        mock_infrared_emitter_entity.entity_id,
        STATE_ON,
        force_update=True,
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 66

    # The fan is known to be running, so turning it on must not toggle it off.
    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls == []


def test_restore_data_rejects_invalid_values() -> None:
    """Test invalid extra stored data is ignored."""
    assert CeilingFanIrRestoreData.from_dict({}) is None
    assert (
        CeilingFanIrRestoreData.from_dict({"is_on": "yes", "percentage": None}) is None
    )
    assert (
        CeilingFanIrRestoreData.from_dict({"is_on": None, "percentage": "low"}) is None
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_state_restored_from_last_state_without_extra_data(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the last state is used when no extra stored data is available."""
    entity_id = "fan.ceiling_fan_via_test_ir_emitter"
    mock_restore_cache(hass, [State(entity_id, STATE_ON, {ATTR_PERCENTAGE: 33})])

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 33


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_invalid_restored_state_is_ignored(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a restored state that is neither on nor off is ignored."""
    entity_id = "fan.ceiling_fan_via_test_ir_emitter"
    mock_restore_cache(hass, [State(entity_id, STATE_UNKNOWN)])

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_PERCENTAGE] is None
