"""Tests for the Ceiling Fan Infrared light platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.ceiling_fan import GenericCeilingFanCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.fixture(autouse=True)
def light_only() -> Generator[None]:
    """Enable only the light platform."""
    with patch(
        "homeassistant.components.ceiling_fan_infrared.PLATFORMS",
        [Platform.LIGHT],
    ):
        yield


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of the light platform."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [
        pytest.param(SERVICE_TURN_ON, STATE_ON, id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, STATE_OFF, id="turn_off"),
    ],
)
@pytest.mark.usefixtures("infrared_codes")
async def test_light_actions(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
    service: str,
    expected_state: str,
) -> None:
    """Test turning the light on and off toggles it with the same code."""
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
        LIGHT_DOMAIN, "ceiling_fan_infrared", f"{config_entry.entry_id}_toggle"
    )
    assert entity_id is not None

    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        GenericCeilingFanCode.LIGHT_TOGGLE
    ]
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == expected_state
