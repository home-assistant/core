"""Test the Panasonic Viera media player entity."""

from datetime import timedelta
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from panasonic_viera import Keys, SOAPError
import pytest

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.panasonic_viera.const import ATTR_UDN, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util.dt import utcnow

from .conftest import MOCK_CONFIG_DATA, MOCK_DEVICE_INFO, MOCK_INPUTS

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "media_player.panasonic_viera_tv"


async def test_media_player_handle_URLerror(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test remote handle URLError as Unavailable."""

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_ON

    # simulate timeout error
    mock_remote.get_mute = Mock(side_effect=URLError(None, None))

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_UNAVAILABLE


async def test_media_player_handle_HTTPError(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test remote handle HTTPError as Off."""

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_ON

    # simulate http badrequest
    mock_remote.get_mute = Mock(side_effect=HTTPError(None, 400, None, None, None))

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)

    state_tv = hass.states.get("media_player.panasonic_viera_tv")
    assert state_tv.state == STATE_OFF


async def test_media_player_select_source(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test the input sources are exposed and can be selected."""

    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.attributes[ATTR_INPUT_SOURCE_LIST] == MOCK_INPUTS
    assert state_tv.attributes[ATTR_INPUT_SOURCE] == MOCK_INPUTS[0]
    assert (
        state_tv.attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.SELECT_SOURCE
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI2"},
        blocking=True,
    )

    mock_remote.set_input.assert_called_once_with("HDMI2")
    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.attributes[ATTR_INPUT_SOURCE] == "HDMI2"


async def test_media_player_select_unknown_source(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test selecting a source the TV does not list is rejected."""
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI9"},
            blocking=True,
        )

    assert err.value.translation_key == "invalid_source"
    mock_remote.set_input.assert_not_called()
    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.state == STATE_ON
    assert state_tv.attributes[ATTR_INPUT_SOURCE] == MOCK_INPUTS[0]


async def test_media_player_current_input_failure(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test a failing input query keeps the TV available and the sources listed."""
    mock_remote.get_input = Mock(side_effect=SOAPError)

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)

    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.state == STATE_ON
    assert state_tv.attributes[ATTR_INPUT_SOURCE_LIST] == MOCK_INPUTS
    assert ATTR_INPUT_SOURCE not in state_tv.attributes


async def test_media_player_select_source_unsupported(
    hass: HomeAssistant, mock_remote: Mock
) -> None:
    """Test a TV without the PAC service does not offer source selection."""
    mock_remote.list_inputs = Mock(side_effect=SOAPError)

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_DEVICE_INFO},
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.state == STATE_ON
    assert ATTR_INPUT_SOURCE_LIST not in state_tv.attributes
    assert not (
        state_tv.attributes[ATTR_SUPPORTED_FEATURES]
        & MediaPlayerEntityFeature.SELECT_SOURCE
    )
    # The PAC service is only probed once
    mock_remote.list_inputs.assert_called_once()
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_remote.list_inputs.assert_called_once()
    mock_remote.get_input.assert_not_called()


async def test_media_player_volume_set(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test the volume can be set."""

    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.25},
        blocking=True,
    )

    mock_remote.set_volume.assert_called_once_with(25)


@pytest.mark.parametrize(
    ("service", "service_data", "key"),
    [
        (SERVICE_VOLUME_UP, {}, Keys.VOLUME_UP.value),
        (SERVICE_VOLUME_DOWN, {}, Keys.VOLUME_DOWN.value),
        (SERVICE_MEDIA_PLAY, {}, Keys.PLAY.value),
        (SERVICE_MEDIA_PAUSE, {}, Keys.PAUSE.value),
        (SERVICE_MEDIA_PLAY_PAUSE, {}, Keys.PAUSE.value),
        (SERVICE_MEDIA_STOP, {}, Keys.STOP.value),
        (SERVICE_MEDIA_NEXT_TRACK, {}, Keys.FAST_FORWARD.value),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, Keys.REWIND.value),
    ],
)
async def test_media_player_key_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_remote: Mock,
    service: str,
    service_data: dict[str, str],
    key: str,
) -> None:
    """Test the key based commands refresh the state of the TV."""
    mock_remote.get_volume.return_value = 40

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_remote.send_key.assert_called_once_with(key)
    state_tv = hass.states.get(ENTITY_ID)
    assert state_tv.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.4


async def test_media_player_mute(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test the TV can be muted."""
    mock_remote.get_mute.return_value = True

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )

    mock_remote.set_mute.assert_called_once_with(True)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_VOLUME_MUTED] is True


async def test_media_player_play_media(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_remote: Mock
) -> None:
    """Test a URL can be opened on the TV."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.URL,
            ATTR_MEDIA_CONTENT_ID: "http://example.com/video",
        },
        blocking=True,
    )

    mock_remote.open_webpage.assert_called_once_with("http://example.com/video")
