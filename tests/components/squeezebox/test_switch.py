"""Tests for the Squeezebox alarm switch platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.squeezebox.const import PLAYER_UPDATE_INTERVAL
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import TEST_ALARM_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def squeezebox_alarm_platform():
    """Only set up the switch platform for squeezebox tests."""
    with patch("homeassistant.components.squeezebox.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.fixture
async def mock_alarms_player(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MagicMock,
) -> MagicMock:
    """Mock the alarms of a configured player."""
    players = await lms.async_get_players()
    players[0].alarms = [
        {
            "id": TEST_ALARM_ID,
            "enabled": True,
            "time": "07:00",
            "dow": [0, 1, 2, 3, 4, 5, 6],
            "repeat": False,
            "url": "CURRENT_PLAYLIST",
            "volume": 50,
        },
    ]

    with patch("homeassistant.components.squeezebox.Server", return_value=lms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return players[0]


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
    assert hass.states.get(f"switch.none_alarm_{TEST_ALARM_ID}").state == "on"

    mock_alarms_player.alarms[0]["enabled"] = False
    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.none_alarm_{TEST_ALARM_ID}").state == "off"


async def test_switch_deleted(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test detecting switch deleted."""
    assert hass.states.get(f"switch.none_alarm_{TEST_ALARM_ID}").state == "on"

    mock_alarms_player.alarms = []
    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.none_alarm_{TEST_ALARM_ID}") is None


async def test_turn_on(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning on the switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: f"switch.none_alarm_{TEST_ALARM_ID}"},
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
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {CONF_ENTITY_ID: f"switch.none_alarm_{TEST_ALARM_ID}"},
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

    assert hass.states.get("switch.none_alarms_enabled").state == "on"

    mock_alarms_player.alarms_enabled = False
    freezer.tick(timedelta(seconds=PLAYER_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.none_alarms_enabled").state == "off"


async def test_alarms_enabled_turn_on(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning on the alarms enabled switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "switch.none_alarms_enabled"},
        blocking=True,
    )
    mock_alarms_player.async_set_alarms_enabled.assert_called_once_with(True)


async def test_alarms_enabled_turn_off(
    hass: HomeAssistant,
    mock_alarms_player: MagicMock,
) -> None:
    """Test turning off the alarms enabled switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {CONF_ENTITY_ID: "switch.none_alarms_enabled"},
        blocking=True,
    )
    mock_alarms_player.async_set_alarms_enabled.assert_called_once_with(False)
