"""Tests for the Ceiling Fan Infrared fan platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.ceiling_fan import GenericCeilingFanCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

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
    Platform,
)
from homeassistant.core import HomeAssistant
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


_FAN_ACTIONS: list[
    tuple[str, dict[str, int], GenericCeilingFanCode, str, int | None]
] = [
    (SERVICE_TURN_ON, {}, GenericCeilingFanCode.FAN_TOGGLE, STATE_ON, 0),
    (
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 0},
        GenericCeilingFanCode.FAN_TOGGLE,
        STATE_OFF,
        0,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 1},
        GenericCeilingFanCode.FAN_LOW,
        STATE_ON,
        33,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 50},
        GenericCeilingFanCode.FAN_MEDIUM,
        STATE_ON,
        66,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 100},
        GenericCeilingFanCode.FAN_HIGH,
        STATE_ON,
        100,
    ),
    (
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 0},
        GenericCeilingFanCode.FAN_TOGGLE,
        STATE_OFF,
        0,
    ),
    (SERVICE_TURN_OFF, {}, GenericCeilingFanCode.FAN_TOGGLE, STATE_OFF, 0),
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
    expected_code: GenericCeilingFanCode,
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
