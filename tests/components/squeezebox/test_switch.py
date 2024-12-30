"""Tests for the Squeezebox alarm switch platform."""

from datetime import datetime, time, timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.squeezebox.const import (
    ATTR_SCHEDULED_TODAY,
    SENSOR_UPDATE_INTERVAL,
)
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
    assert hass.states.get("switch.squeezebox_alarm_1").state == "on"

    mock_alarms_player.alarms[0]["enabled"] = False
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.squeezebox_alarm_1").state == "off"

    mock_alarms_player.connected = False
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.squeezebox_alarm_1").state == "unavailable"


async def test_daily_update(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test daily update of the switch."""
    assert (
        hass.states.get("switch.squeezebox_alarm_1").attributes[ATTR_SCHEDULED_TODAY]
        is True
    )
    tomorrow = datetime.today().weekday() + 1
    mock_alarms_player.alarms[0]["dow"].remove(tomorrow)

    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        hass.states.get("switch.squeezebox_alarm_1").attributes[ATTR_SCHEDULED_TODAY]
        is False
    )


async def test_switch_deleted(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test detecting switch deleted."""
    assert hass.states.get("switch.squeezebox_alarm_1").state == "on"

    mock_alarms_player.alarms = []
    freezer.tick(timedelta(seconds=SENSOR_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.squeezebox_alarm_1") is None


async def test_turn_on(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning on the switch."""
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.squeezebox_alarm_1"},
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
        {"entity_id": "switch.squeezebox_alarm_1"},
        blocking=True,
    )
    mock_alarms_player.async_update_alarm.assert_called_once_with(
        TEST_ALARM_ID, enabled=False
    )


async def test_delete_alarm(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test deleting the alarm."""
    await hass.services.async_call(
        "squeezebox",
        "delete_alarm",
        {"entity_id": "switch.squeezebox_alarm_1"},
        blocking=True,
    )
    mock_alarms_player.async_delete_alarm.assert_called_once_with(TEST_ALARM_ID)


async def test_update_alarm(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test updating the alarm."""
    alarm = mock_alarms_player.alarms[0]
    await hass.services.async_call(
        "squeezebox",
        "update_alarm",
        {"entity_id": "switch.squeezebox_alarm_1", "time": "08:00"},
        blocking=True,
    )
    mock_alarms_player.async_update_alarm.assert_called_once_with(
        TEST_ALARM_ID,
        dow=alarm["dow"],
        enabled=alarm["enabled"],
        repeat=alarm["repeat"],
        time=time(hour=8),
        volume=alarm["volume"],
        url=alarm["url"],
    )
