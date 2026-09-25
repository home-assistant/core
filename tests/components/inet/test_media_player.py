"""Test the iNet Radio media player platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.inet.media_player import SOURCE_AUX, SOURCE_UPNP
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import MOCK_NAME, _create_mock_station

ENTITY_ID = f"media_player.{MOCK_NAME.lower().replace(' ', '_')}"


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry,
    mock_manager,
    mock_radio,
) -> None:
    """Set up the iNet integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_media_player_state_off(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test media player shows off state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_media_player_state_playing(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test media player shows playing state when radio is on with station."""
    mock_radio.power = True
    mock_radio.playing_mode = "STATION"
    mock_radio.playing_station_name = "SWR3"

    # Trigger callback
    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_PLAYING
    assert state.attributes["media_title"] == "SWR3"


@pytest.mark.usefixtures("init_integration")
async def test_media_player_state_idle(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test media player shows idle state when on but not playing."""
    mock_radio.power = True
    mock_radio.playing_mode = ""

    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_IDLE


@pytest.mark.usefixtures("init_integration")
async def test_turn_on(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test turning on the radio."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_manager.turn_on.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test turning off the radio."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_manager.turn_off.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_set_volume(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test setting volume level."""
    await hass.services.async_call(
        MP_DOMAIN,
        "volume_set",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    # 0.5 * 31 = 15.5, rounded to 16
    mock_manager.set_volume.assert_called_once_with(mock_radio, 16)


@pytest.mark.usefixtures("init_integration")
async def test_mute(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test muting the radio."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_manager.mute.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_unmute(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test unmuting the radio."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: False},
        blocking=True,
    )
    mock_manager.unmute.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_volume_up(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test volume up."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_manager.volume_up.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_volume_down(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test volume down."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_manager.volume_down.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_select_source_station(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test selecting a station source."""
    mock_radio.stations = [
        _create_mock_station(1, "SWR3", "http://swr3.de/stream"),
        _create_mock_station(2, "WDR 2", "http://wdr2.de/stream"),
    ]

    # Trigger update to refresh source list
    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "SWR3"},
        blocking=True,
    )
    mock_manager.play_station.assert_called_once_with(mock_radio, 1)


@pytest.mark.usefixtures("init_integration")
async def test_select_source_aux(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test selecting AUX source."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: SOURCE_AUX},
        blocking=True,
    )
    mock_manager.play_aux.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_select_source_upnp(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test selecting UPnP source."""
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: SOURCE_UPNP},
        blocking=True,
    )
    mock_manager.play_upnp.assert_called_once_with(mock_radio)


@pytest.mark.usefixtures("init_integration")
async def test_source_list_with_stations(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test source list includes stations, AUX, and UPnP."""
    mock_radio.stations = [
        _create_mock_station(1, "SWR3", "http://swr3.de/stream"),
        _create_mock_station(2, "", "http://example.com/stream"),
    ]

    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    source_list = state.attributes["source_list"]
    assert "SWR3" in source_list
    assert "Station 2" in source_list
    assert SOURCE_AUX in source_list
    assert SOURCE_UPNP in source_list


@pytest.mark.usefixtures("init_integration")
async def test_volume_level_attribute(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test volume level is properly scaled (0-31 -> 0.0-1.0)."""
    mock_radio.volume = 15
    mock_radio.power = True
    mock_radio.playing_mode = "STATION"

    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    # 15 / 31 ≈ 0.484
    assert abs(state.attributes["volume_level"] - 15 / 31) < 0.01


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_state(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test entity becomes unavailable when radio is not available."""
    mock_radio.available = False

    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("init_integration")
async def test_select_source_invalid(
    hass: HomeAssistant,
    mock_radio: MagicMock,
) -> None:
    """Test selecting an invalid source raises an error."""
    mock_radio.stations = [
        _create_mock_station(1, "SWR3", "http://swr3.de/stream"),
    ]

    for cb in mock_radio._callbacks:
        cb()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "Nonexistent Radio"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_action_communication_error(
    hass: HomeAssistant,
    mock_manager: AsyncMock,
    mock_radio: MagicMock,
) -> None:
    """Test that OSError during an action raises HomeAssistantError."""
    mock_manager.turn_on.side_effect = OSError("Network unreachable")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
