"""Tests for the Qube Heat Pump switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

HEATING_DEMAND_KEY = "heating_demand"


def _get_entity_id(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry, key: str
) -> str:
    """Look up entity_id by key and config entry."""
    unique_id = f"{entry.entry_id}-{key}"
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "hr_energy_qube", unique_id
    )
    assert entity_id is not None
    return entity_id


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all switch entities via snapshot."""
    with patch(
        "homeassistant.components.hr_energy_qube.PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "expected_value"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_value: bool,
) -> None:
    """Test turning a switch on and off."""
    await setup_integration(hass, mock_config_entry)

    entity_id = _get_entity_id(entity_registry, mock_config_entry, HEATING_DEMAND_KEY)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_qube_client.write_switch.assert_awaited_once_with(
        "modbus_demand", expected_value
    )


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError, None),
        (None, False),
    ],
)
async def test_turn_on_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    return_value: bool | None,
) -> None:
    """Test switch raises HomeAssistantError on write failure."""
    await setup_integration(hass, mock_config_entry)

    mock_qube_client.write_switch = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )
    entity_id = _get_entity_id(entity_registry, mock_config_entry, HEATING_DEMAND_KEY)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("side_effect", "return_value"),
    [
        (ConnectionError("Connection lost"), None),
        (None, None),
    ],
)
async def test_switch_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception | None,
    return_value: None,
) -> None:
    """Test switches become unavailable when coordinator fails."""
    await setup_integration(hass, mock_config_entry)

    # Verify switches are available after setup
    states = hass.states.async_all("switch")
    assert len(states) > 0
    assert all(s.state != STATE_UNAVAILABLE for s in states)

    # Make the next fetch fail
    mock_qube_client.get_all_data = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )

    # Skip time to trigger coordinator refresh
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # All switches should be unavailable
    states = hass.states.async_all("switch")
    assert all(s.state == STATE_UNAVAILABLE for s in states)


async def test_switch_retains_state_on_switch_read_failure(
    hass: HomeAssistant,
    mock_qube_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switches retain previous state when read_all_switches fails."""
    await setup_integration(hass, mock_config_entry)

    # Record initial switch states
    switch_states_before = {
        s.entity_id: s.state for s in hass.states.async_all("switch")
    }
    assert len(switch_states_before) > 0
    assert all(s != STATE_UNAVAILABLE for s in switch_states_before.values())

    # Make only switch reads fail, sensor data succeeds
    mock_qube_client.read_all_switches = AsyncMock(
        side_effect=ConnectionError("Switch read failed")
    )

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensors should still be available
    sensor_states = hass.states.async_all("sensor")
    assert all(s.state != STATE_UNAVAILABLE for s in sensor_states)

    # Switches should retain their previous on/off states
    for entity_id, previous_state in switch_states_before.items():
        current = hass.states.get(entity_id)
        assert current is not None
        assert current.state == previous_state
