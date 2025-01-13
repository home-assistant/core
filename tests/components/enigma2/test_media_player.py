"""Tests for the media player module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from openwebif.api import OpenWebIfServiceEvent, OpenWebIfStatus
from openwebif.enums import PowerState, RemoteControlCodes, SetVolumeOption
import pytest

from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.components.enigma2.media_player import ATTR_MEDIA_CURRENTLY_RECORDING
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)


@pytest.mark.parametrize(
    ("deep_standby", "powerstate"),
    [(False, PowerState.STANDBY), (True, PowerState.DEEP_STANDBY)],
)
async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
    deep_standby: bool,
    powerstate: PowerState,
) -> None:
    """Test turning off the media player."""
    openwebif_device_mock.turn_off_to_deep = deep_standby
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "media_player.1_1_1_1"}
    )

    openwebif_device_mock.set_powerstate.assert_awaited_once_with(powerstate)


async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
) -> None:
    """Test turning on the media player."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "media_player.1_1_1_1"}
    )

    openwebif_device_mock.turn_on.assert_awaited_once()


async def test_set_volume_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
) -> None:
    """Test setting the volume of the media player."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.1_1_1_1", ATTR_MEDIA_VOLUME_LEVEL: 0.2},
    )

    openwebif_device_mock.set_volume.assert_awaited_once_with(20)


async def test_volume_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
) -> None:
    """Test increasing the volume of the media player."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: "media_player.1_1_1_1"}
    )

    openwebif_device_mock.set_volume.assert_awaited_once_with(SetVolumeOption.UP)


async def test_volume_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
) -> None:
    """Test decreasing the volume of the media player."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.1_1_1_1"},
    )

    openwebif_device_mock.set_volume.assert_awaited_once_with(SetVolumeOption.DOWN)


@pytest.mark.parametrize(
    ("service", "remote_code"),
    [
        (SERVICE_MEDIA_STOP, RemoteControlCodes.STOP),
        (SERVICE_MEDIA_PLAY, RemoteControlCodes.PLAY),
        (SERVICE_MEDIA_PAUSE, RemoteControlCodes.PAUSE),
        (SERVICE_MEDIA_NEXT_TRACK, RemoteControlCodes.CHANNEL_UP),
        (SERVICE_MEDIA_PREVIOUS_TRACK, RemoteControlCodes.CHANNEL_DOWN),
    ],
)
async def test_remote_control_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
    service: str,
    remote_code: RemoteControlCodes,
) -> None:
    """Test media stop."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "media_player.1_1_1_1"},
    )

    openwebif_device_mock.send_remote_control_action.assert_awaited_once_with(
        remote_code
    )


@pytest.mark.parametrize("mute", [False, True])
async def test_volume_mute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
    mute: bool,
) -> None:
    """Test mute."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.1_1_1_1", ATTR_MEDIA_VOLUME_MUTED: mute},
    )

    openwebif_device_mock.toggle_mute.assert_awaited_once()


async def test_select_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
) -> None:
    """Test media previous track."""
    openwebif_device_mock.return_value.sources = {"Test": "1"}

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.1_1_1_1", ATTR_INPUT_SOURCE: "Test"},
    )

    openwebif_device_mock.zap.assert_awaited_once_with("1")


async def test_update_data_standby(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test data handling."""

    openwebif_device_mock.get_status_info.return_value = load_json_object_fixture(
        "device_statusinfo_standby.json", DOMAIN
    )
    openwebif_device_mock.status = OpenWebIfStatus(
        currservice=OpenWebIfServiceEvent(), in_standby=True
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        ATTR_MEDIA_CURRENTLY_RECORDING
        not in hass.states.get("media_player.1_1_1_1").attributes
    )
    assert hass.states.get("media_player.1_1_1_1").state == MediaPlayerState.OFF


async def test_update_volume(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test volume data handling."""

    openwebif_device_mock.status = OpenWebIfStatus(
        currservice=OpenWebIfServiceEvent(), in_standby=False, volume=100
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("media_player.1_1_1_1").attributes[ATTR_MEDIA_VOLUME_LEVEL]
        > 0.99
    )


async def test_update_volume_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    openwebif_device_mock: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test volume data handling."""

    openwebif_device_mock.status = OpenWebIfStatus(
        currservice=OpenWebIfServiceEvent(), in_standby=False, volume=None
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        ATTR_MEDIA_VOLUME_LEVEL
        not in hass.states.get("media_player.1_1_1_1").attributes
    )
