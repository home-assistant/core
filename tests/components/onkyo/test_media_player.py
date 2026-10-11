"""Test Onkyo media player platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioonkyo import Code, Instruction, Kind, Zone, command, query, status
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.onkyo.media_player import (
    QUERY_AV_INFO_DELAY,
    QUERY_STATE_DELAY,
)
from homeassistant.components.onkyo.services import (
    ATTR_HDMI_OUTPUT,
    SERVICE_SELECT_HDMI_OUTPUT,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import DISCONNECT, receive_messages, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "media_player.tx_nr7100"
ENTITY_ID_ZONE_2 = "media_player.tx_nr7100_zone_2"
ENTITY_ID_ZONE_3 = "media_player.tx_nr7100_zone_3"


@pytest.fixture(autouse=True)
async def auto_setup_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_receiver: AsyncMock,
    writes: list[Instruction],
) -> AsyncGenerator[None]:
    """Auto setup integration."""
    with patch("homeassistant.components.onkyo.PLATFORMS", [Platform.MEDIA_PLAYER]):
        await setup_integration(hass, mock_config_entry)

        # Let the delayed queries triggered by the initial messages run
        freezer.tick(timedelta(seconds=max(QUERY_STATE_DELAY, QUERY_AV_INFO_DELAY)))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        writes.clear()
        yield


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(hass: HomeAssistant, read_queue: asyncio.Queue) -> None:
    """Test entity availability on disconnect and reconnect."""
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE

    await receive_messages(read_queue, DISCONNECT)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate first status update after reconnect
    await receive_messages(
        read_queue,
        status.Power(
            Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
        ),
    )

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("action", "action_data", "message"),
    [
        (SERVICE_TURN_ON, {}, command.Power(Zone.MAIN, command.Power.Param.ON)),
        (SERVICE_TURN_OFF, {}, command.Power(Zone.MAIN, command.Power.Param.STANDBY)),
        (
            SERVICE_VOLUME_SET,
            {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            command.Volume(Zone.MAIN, 40),
        ),
        (SERVICE_VOLUME_UP, {}, command.Volume(Zone.MAIN, command.Volume.Param.UP)),
        (SERVICE_VOLUME_DOWN, {}, command.Volume(Zone.MAIN, command.Volume.Param.DOWN)),
        (
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
            command.Muting(Zone.MAIN, command.Muting.Param.ON),
        ),
        (
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: False},
            command.Muting(Zone.MAIN, command.Muting.Param.OFF),
        ),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    writes: list[Instruction],
    action: str,
    action_data: dict,
    message: Instruction,
) -> None:
    """Test actions."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        action,
        {ATTR_ENTITY_ID: ENTITY_ID, **action_data},
        blocking=True,
    )
    assert writes[0] == message


async def test_select_source(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test select source."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "TV"},
        blocking=True,
    )
    assert writes[0] == command.InputSource(Zone.MAIN, command.InputSource.Param("12"))

    writes.clear()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "InvalidSource"},
            blocking=True,
        )
    assert not writes


async def test_select_sound_mode(
    hass: HomeAssistant, writes: list[Instruction]
) -> None:
    """Test select sound mode."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "THX"},
        blocking=True,
    )
    assert writes[0] == command.ListeningMode(
        Zone.MAIN, command.ListeningMode.Param("04")
    )

    writes.clear()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "InvalidMode"},
            blocking=True,
        )
    assert not writes


async def test_play_media(hass: HomeAssistant, writes: list[Instruction]) -> None:
    """Test play media (radio preset)."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "radio",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert writes[0] == command.TunerPreset(Zone.MAIN, 5)

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert not writes

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID_ZONE_2,
            ATTR_MEDIA_CONTENT_TYPE: "radio",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert not writes

    writes.clear()
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID_ZONE_3,
            ATTR_MEDIA_CONTENT_TYPE: "radio",
            ATTR_MEDIA_CONTENT_ID: "5",
        },
        blocking=True,
    )
    assert not writes


async def test_select_hdmi_output(
    hass: HomeAssistant, writes: list[Instruction]
) -> None:
    """Test select hdmi output."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_HDMI_OUTPUT,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HDMI_OUTPUT: "sub"},
        blocking=True,
    )
    assert writes[0] == command.HDMIOutput(command.HDMIOutput.Param.BOTH)


async def test_query_state_delayed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test state query."""
    power_standby = status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.STANDBY
    )
    power_on = status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
    )

    await receive_messages(read_queue, power_standby, power_on)

    freezer.tick(timedelta(seconds=QUERY_STATE_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Powering on again restarts the delay
    await receive_messages(read_queue, power_standby, power_on)

    freezer.tick(timedelta(seconds=QUERY_STATE_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.Volume)]
    assert not queries

    freezer.tick(timedelta(seconds=QUERY_STATE_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.Volume)]
    assert len(queries) == 1


async def test_query_av_info_delayed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test AV info query."""
    await receive_messages(
        read_queue,
        status.InputSource(
            Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.MAIN),
            None,
            status.InputSource.Param("24"),
        ),
    )

    freezer.tick(timedelta(seconds=QUERY_AV_INFO_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Another source change while a query is pending does not restart the delay
    await receive_messages(
        read_queue,
        status.InputSource(
            Code.from_kind_zone(Kind.INPUT_SOURCE, Zone.MAIN),
            None,
            status.InputSource.Param("00"),
        ),
    )

    freezer.tick(timedelta(seconds=QUERY_AV_INFO_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.AudioInformation)]
    assert len(queries) == 1
