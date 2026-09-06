"""Test Lutron cover platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def setup_platforms():
    """Patch PLATFORMS for all tests in this file."""
    with patch("homeassistant.components.lutron.PLATFORMS", [Platform.COVER]):
        yield


async def test_cover_setup(
    hass: HomeAssistant,
    mock_lutron: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test cover setup."""
    mock_config_entry.add_to_hass(hass)

    cover = mock_lutron.areas[0].outputs[2]
    cover.level = 0
    cover.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_cover_services(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test cover services."""
    mock_config_entry.add_to_hass(hass)

    cover = mock_lutron.areas[0].outputs[2]
    cover.level = 0
    cover.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_area_test_cover"

    # Open cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert cover.level == 100

    # Close cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert cover.level == 0

    # Set cover position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, "position": 50},
        blocking=True,
    )
    assert cover.level == 50


async def test_cover_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test cover state update."""
    mock_config_entry.add_to_hass(hass)

    cover = mock_lutron.areas[0].outputs[2]
    cover.level = 0
    cover.last_level.return_value = 0

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_area_test_cover"
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # Simulate update
    cover.last_level.return_value = 100
    callback = cover.subscribe.call_args[0][0]
    callback(cover, None, None, None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OPEN
    assert hass.states.get(entity_id).attributes["current_position"] == 100


def _mock_output(name: str, output_id: int, output_type: str) -> MagicMock:
    """Build a pylutron Output mock the way conftest does."""
    output = MagicMock()
    output.name = name
    output.id = output_id
    output.uuid = f"{name.lower().replace(' ', '_')}_uuid"
    output.legacy_uuid = f"{name.lower().replace(' ', '_')}_legacy_uuid"
    output.type = output_type
    output.last_level.return_value = 0

    def _set_level(new_level, fade_time_seconds=None):
        output.last_level.return_value = new_level

    output.set_level.side_effect = _set_level
    return output


async def test_sivoia_qed_cover_services(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A SIVOIA_QED output is a position-capable cover, like SYSTEM_SHADE."""
    mock_config_entry.add_to_hass(hass)
    qed = _mock_output("Test QED Shade", 10, "SIVOIA_QED")
    mock_lutron.areas[0].outputs.append(qed)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_area_test_qed_shade"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    # and it is NOT a light any more
    assert hass.states.get("light.test_area_test_qed_shade") is None

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert qed.level == 100
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, "position": 40},
        blocking=True,
    )
    assert qed.level == 40
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert qed.level == 0


async def test_motor_cover_services(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A MOTOR output is a raise/lower/stop cover without position control."""
    mock_config_entry.add_to_hass(hass)
    motor = _mock_output("Test Motor", 11, "MOTOR")
    mock_lutron.areas[0].outputs.append(motor)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_area_test_motor"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    assert state.attributes[ATTR_ASSUMED_STATE] is True
    assert hass.states.get("switch.test_area_test_motor") is None

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    motor.start_raise.assert_called_once()
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    motor.start_lower.assert_called_once()
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    motor.stop.assert_called_once()
    # the repeater ignores "set level" on motors and pylutron>=0.4.2 raises on it
    motor.set_level.assert_not_called()


async def test_motor_cover_update(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Position reports from the repeater drive the motor cover's state."""
    mock_config_entry.add_to_hass(hass)
    motor = _mock_output("Test Motor", 11, "MOTOR")
    mock_lutron.areas[0].outputs.append(motor)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "cover.test_area_test_motor"
    assert hass.states.get(entity_id).state == STATE_CLOSED

    motor.last_level.return_value = 100
    callback = motor.subscribe.call_args[0][0]
    callback(motor, None, None, None)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100
