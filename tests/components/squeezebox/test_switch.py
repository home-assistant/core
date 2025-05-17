"""Tests for the Squeezebox alarm switch platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.squeezebox.const import SENSOR_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import TEST_ALARM_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    mock_alarms_player: MagicMock,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
) -> None:
    """Test squeezebox media_player entity registered in the entity registry."""
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_state(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the state of the switch."""
    assert hass.states.get(f"switch.test_player_alarm_{TEST_ALARM_ID}").state == "on"

    mock_alarms_player.alarms[0]["enabled"] = False
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.test_player_alarm_{TEST_ALARM_ID}").state == "off"


async def test_switch_deleted(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test detecting switch deleted."""
    assert hass.states.get(f"switch.test_player_alarm_{TEST_ALARM_ID}").state == "on"

    mock_alarms_player.alarms = []
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.test_player_alarm_{TEST_ALARM_ID}") is None


async def test_turn_on(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning on the switch."""
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": f"switch.test_player_alarm_{TEST_ALARM_ID}"},
        blocking=True,
    )
    mock_alarms_player.async_update_alarm.assert_called_once_with(
        TEST_ALARM_ID, enabled=True
    )


async def test_turn_off(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning on the switch."""
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": f"switch.test_player_alarm_{TEST_ALARM_ID}"},
        blocking=True,
    )
    mock_alarms_player.async_update_alarm.assert_called_once_with(
        TEST_ALARM_ID, enabled=False
    )


async def test_alarms_enabled_state(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the alarms enabled switch."""

    assert hass.states.get("switch.test_player_alarms_enabled").state == "on"

    mock_alarms_player.alarms_enabled = False
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_player_alarms_enabled").state == "off"


async def test_alarms_enabled_turn_on(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning on the alarms enabled switch."""
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.test_player_alarms_enabled"},
        blocking=True,
    )
    mock_alarms_player.async_set_alarms_enabled.assert_called_once_with(True)


async def test_alarms_enabled_turn_off(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning off the alarms enabled switch."""
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.test_player_alarms_enabled"},
        blocking=True,
    )
    mock_alarms_player.async_set_alarms_enabled.assert_called_once_with(False)
