"""Tests for the Lyngdorf number platform."""

from unittest.mock import MagicMock

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

LIPSYNC_ENTITY_ID = "number.mock_lyngdorf_lip_sync"
TRIM_BASS_ENTITY_ID = "number.mock_lyngdorf_trim_bass"
TRIM_TREBLE_ENTITY_ID = "number.mock_lyngdorf_trim_treble"
TRIM_CENTRE_ENTITY_ID = "number.mock_lyngdorf_trim_centre"
TRIM_HEIGHT_ENTITY_ID = "number.mock_lyngdorf_trim_height"
TRIM_LFE_ENTITY_ID = "number.mock_lyngdorf_trim_lfe"
TRIM_SURROUND_ENTITY_ID = "number.mock_lyngdorf_trim_surround"


async def test_number_entities_created(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test that number entities are created."""
    assert init_integration.state.value == "loaded"

    for entity_id in (
        LIPSYNC_ENTITY_ID,
        TRIM_BASS_ENTITY_ID,
        TRIM_TREBLE_ENTITY_ID,
        TRIM_CENTRE_ENTITY_ID,
        TRIM_HEIGHT_ENTITY_ID,
        TRIM_LFE_ENTITY_ID,
        TRIM_SURROUND_ENTITY_ID,
    ):
        assert hass.states.get(entity_id) is not None, f"{entity_id} not found"


async def test_number_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test that number entities reflect receiver values."""
    mock_receiver.lipsync = 50
    mock_receiver.trim_bass = -3.0
    mock_receiver.trim_treble = 1.5
    mock_receiver.trim_centre = -2.0
    mock_receiver.trim_height = 0.0
    mock_receiver.trim_lfe = 5.0
    mock_receiver.trim_surround = -1.0

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    assert hass.states.get(LIPSYNC_ENTITY_ID).state == "50.0"
    assert hass.states.get(TRIM_BASS_ENTITY_ID).state == "-3.0"
    assert hass.states.get(TRIM_TREBLE_ENTITY_ID).state == "1.5"
    assert hass.states.get(TRIM_CENTRE_ENTITY_ID).state == "-2.0"
    assert hass.states.get(TRIM_HEIGHT_ENTITY_ID).state == "0.0"
    assert hass.states.get(TRIM_LFE_ENTITY_ID).state == "5.0"
    assert hass.states.get(TRIM_SURROUND_ENTITY_ID).state == "-1.0"


async def test_set_lipsync(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test setting the lipsync value."""
    mock_receiver.lipsync = 0

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: LIPSYNC_ENTITY_ID,
            "value": 75,
        },
        blocking=True,
    )

    assert mock_receiver.lipsync == 75


async def test_set_trim_bass(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test setting a trim value."""
    mock_receiver.trim_bass = 0.0

    callbacks = [
        call.args[0]
        for call in mock_receiver.register_notification_callback.call_args_list
    ]
    for cb in callbacks:
        cb()
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: TRIM_BASS_ENTITY_ID,
            "value": -6.0,
        },
        blocking=True,
    )

    assert mock_receiver.trim_bass == -6.0


async def test_number_none_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test number entities show unknown when receiver values are None."""
    state = hass.states.get(LIPSYNC_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get(TRIM_BASS_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
