"""Tests for the Dyson Infrared fan platform."""

from unittest.mock import call, patch

from infrared_protocols.codes.dyson.cool import DysonCoolCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dyson_infrared.const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_DEVICE_TYPE,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DOMAIN,
    DysonDeviceType,
)
from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared import EMITTER_ENTITY_ID as MOCK_INFRARED_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fan entity is created with correct attributes and attached to a device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        ("dyson_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_sends_on_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
) -> None:
    """Test turning on without a percentage sends the ON code."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonCoolCode.ON]

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.state == "on"


@pytest.mark.usefixtures("init_integration")
async def test_turn_off_sends_off_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
) -> None:
    """Test turning off sends the OFF code."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonCoolCode.OFF]

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.state == "off"


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_percentage_equal_to_current_speed(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
) -> None:
    """Test turning on at the fan's already-tracked percentage still sends ON.

    The fan starts off at 50%. Turning it on while requesting the same 50%
    must still emit the ON command instead of silently doing nothing,
    since the fan is physically off at this point.
    """
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonCoolCode.ON]

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_PERCENTAGE] == 50


@pytest.mark.usefixtures("init_integration")
async def test_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
) -> None:
    """Test setting percentage to zero turns off the fan."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonCoolCode.OFF]

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.state == "off"


@pytest.mark.parametrize(
    ("requested_percentage", "expected_codes", "expected_percentage"),
    [
        # 40% -> 80%: 4 discrete speed steps up (levels 4 -> 8)
        (80, [DysonCoolCode.SPEED_UP] * 4, 80),
        # 55% rounds to speed level 6 (60%): 2 steps up from level 4 (40%),
        # and the *normalized* 60% must be stored, not the raw 55% requested.
        (55, [DysonCoolCode.SPEED_UP] * 2, 60),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_percentage_speed_up(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
    requested_percentage: int,
    expected_codes: list[DysonCoolCode],
    expected_percentage: int,
) -> None:
    """Test increasing percentage sends the correct number of speed_up codes.

    The fan starts at 50%. Requesting a percentage that maps to the same
    discrete speed level after rounding (e.g. 55%) must still send at
    least one command when the level actually changes, and must store
    the normalized percentage rather than the raw requested value.
    """
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 40},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: requested_percentage},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == expected_codes

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage


@pytest.mark.usefixtures("init_integration")
async def test_set_percentage_speed_down(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
) -> None:
    """Test decreasing percentage sends the correct number of speed_down codes."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 90},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 30},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == (
        [DysonCoolCode.SPEED_DOWN] * 6
    )

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.attributes[ATTR_PERCENTAGE] == 30


@pytest.mark.usefixtures("init_integration")
async def test_oscillate_sends_swing_command(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_entity_id: str,
) -> None:
    """Test oscillating sends the SWING code and updates state."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_OSCILLATING: True},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [DysonCoolCode.SWING]

    state = hass.states.get(fan_entity_id)
    assert state
    assert state.attributes[ATTR_OSCILLATING] is True


async def test_custom_command_step_delay_is_used_when_stepping(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_make_dyson_cool_command: None,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a configured command_step_delay is used as the inter-command delay."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DEVICE_TYPE: DysonDeviceType.FAN,
            CONF_INFRARED_EMITTER_ENTITY_ID: MOCK_INFRARED_ENTITY_ID,
            CONF_COMMAND_STEP_DELAY: 1.5,
        },
        unique_id="fan_test",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    fan_entity_id = entities[0].entity_id

    with patch(
        "homeassistant.components.dyson_infrared.fan.asyncio.sleep"
    ) as mock_sleep:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 80},
            blocking=True,
        )

    # Stepping speed 5 to 8 sends three commands, delayed only between them.
    assert mock_sleep.call_args_list == [call(1.5), call(1.5)]
