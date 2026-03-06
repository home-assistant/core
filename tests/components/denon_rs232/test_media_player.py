"""Tests for the Denon RS232 media player platform."""

from unittest.mock import MagicMock, patch

from denon_rs232 import DenonState, InputSource, PowerState

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .conftest import _default_state

ENTITY_ID = "media_player.denon_receiver"


async def _setup_integration(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    mock_config_entry,
) -> None:
    """Set up the integration with a mock receiver."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.denon_rs232.DenonReceiver",
        return_value=mock_receiver,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_entity_created(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test media player entity is created with correct state."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_state_on(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test state is ON when receiver is powered on."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_state_off(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test state is OFF when receiver is in standby."""
    mock_receiver.state = DenonState(power=PowerState.STANDBY)
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_volume_level(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test volume level is correctly converted from dB to 0..1."""
    # -30 dB: ((-30) - (-80)) / 98 = 50 / 98 ≈ 0.5102
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    volume = state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert abs(volume - 50.0 / 98.0) < 0.001


async def test_mute_state(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test mute state is reported."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False


async def test_source(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test current source is reported."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "cd"


async def test_source_net(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test NET source is reported with the translation key."""
    mock_receiver.state = DenonState(power=PowerState.ON, input_source=InputSource.NET)
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "net"


async def test_source_bluetooth(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test BT source is reported with the translation key."""
    mock_receiver.state = DenonState(power=PowerState.ON, input_source=InputSource.BT)
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "bt"


async def test_source_list(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test source list comes from the model definition."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    source_list = state.attributes[ATTR_INPUT_SOURCE_LIST]
    # AVR-3805 has the legacy sources (no VCR-3, no MD/TAPE2)
    assert "cd" in source_list
    assert "dvd" in source_list
    assert "tuner" in source_list
    # Should be sorted
    assert source_list == sorted(source_list)


async def test_sound_mode(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test surround mode is reported as sound mode."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SOUND_MODE] == "stereo"


async def test_sound_mode_list(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test sound mode list comes from the model definition."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    mode_list = state.attributes[ATTR_SOUND_MODE_LIST]
    assert "direct" in mode_list
    assert "stereo" in mode_list
    assert "dolby_digital" in mode_list


async def test_turn_on(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test turning on the receiver."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.power_on.assert_awaited_once()


async def test_turn_off(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test turning off the receiver."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.power_standby.assert_awaited_once()


async def test_set_volume(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test setting volume level converts from 0..1 to dB."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    # 0.5 * 98 + (-80) = -31.0
    mock_receiver.set_volume.assert_awaited_once_with(-31.0)


async def test_volume_up(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test volume up."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.volume_up.assert_awaited_once()


async def test_volume_down(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test volume down."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_receiver.volume_down.assert_awaited_once()


async def test_mute(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test muting."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_receiver.mute_on.assert_awaited_once()


async def test_unmute(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test unmuting."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    mock_receiver.mute_off.assert_awaited_once()


async def test_select_source(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting input source."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "dvd"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.DVD)


async def test_select_source_net(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting NET source."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "net"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.NET)


async def test_select_source_bluetooth(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting BT source."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "bt"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.BT)


async def test_select_source_raw_value(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting a raw protocol source value still works."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "DVD"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_awaited_once_with(InputSource.DVD)


async def test_select_source_unknown(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting an unknown source does nothing."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "NONEXISTENT"},
        blocking=True,
    )
    mock_receiver.select_input_source.assert_not_awaited()


async def test_select_sound_mode(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting sound mode."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "dolby_digital"},
        blocking=True,
    )
    mock_receiver.set_surround_mode.assert_awaited_once_with("DOLBY DIGITAL")


async def test_select_sound_mode_raw_value(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test selecting a raw protocol sound mode value still works."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SOUND_MODE: "DOLBY DIGITAL"},
        blocking=True,
    )
    mock_receiver.set_surround_mode.assert_awaited_once_with("DOLBY DIGITAL")


async def test_push_update(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test state updates from the receiver via subscribe callback."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    # Get the callback that was passed to subscribe()
    # The __init__.py subscribe is call [0], media_player subscribe is call [1]
    media_player_subscribe = mock_receiver.subscribe.call_args_list[1]
    callback = media_player_subscribe[0][0]

    # Simulate a state change from the receiver
    new_state = _default_state()
    new_state.volume = -20.0
    new_state.input_source = InputSource.DVD
    new_state.surround_mode = "DOLBY DIGITAL"

    callback(new_state)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_INPUT_SOURCE] == "dvd"
    assert state.attributes[ATTR_SOUND_MODE] == "dolby_digital"
    expected_volume = ((-20.0) - (-80.0)) / 98.0
    assert abs(state.attributes[ATTR_MEDIA_VOLUME_LEVEL] - expected_volume) < 0.001


async def test_push_disconnect(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test entity becomes unavailable on disconnect."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    media_player_subscribe = mock_receiver.subscribe.call_args_list[1]
    callback = media_player_subscribe[0][0]

    # Simulate disconnect (callback receives None)
    callback(None)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unavailable"


async def test_push_reconnect(
    hass: HomeAssistant, mock_receiver, mock_config_entry
) -> None:
    """Test entity becomes available again after disconnect and reconnect."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    media_player_subscribe = mock_receiver.subscribe.call_args_list[1]
    callback = media_player_subscribe[0][0]

    # Disconnect
    callback(None)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unavailable"

    # Reconnect with new state
    callback(_default_state())
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def test_unload(hass: HomeAssistant, mock_receiver, mock_config_entry) -> None:
    """Test unloading the integration disconnects the receiver."""
    await _setup_integration(hass, mock_receiver, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_receiver.disconnect.assert_awaited_once()
