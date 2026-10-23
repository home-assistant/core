"""Test the Panasonic Viera media player entity."""

from datetime import timedelta
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

from panasonic_viera import SOAPError

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
)
from homeassistant.components.panasonic_viera.const import ATTR_UDN, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
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
