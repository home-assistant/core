"""Tests for the Lyngdorf number platform."""

from unittest.mock import MagicMock, patch

from lyngdorf.const import LyngdorfModel
import pytest

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .conftest import notify_receiver_update

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

    notify_receiver_update(mock_receiver)
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

    notify_receiver_update(mock_receiver)
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


@pytest.mark.parametrize(
    ("entity_id", "attribute"),
    [
        pytest.param(TRIM_BASS_ENTITY_ID, "trim_bass", id="bass"),
        pytest.param(TRIM_TREBLE_ENTITY_ID, "trim_treble", id="treble"),
        pytest.param(TRIM_CENTRE_ENTITY_ID, "trim_centre", id="centre"),
        pytest.param(TRIM_HEIGHT_ENTITY_ID, "trim_height", id="height"),
        pytest.param(TRIM_LFE_ENTITY_ID, "trim_lfe", id="lfe"),
        pytest.param(TRIM_SURROUND_ENTITY_ID, "trim_surround", id="surround"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_set_trim(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    entity_id: str,
    attribute: str,
) -> None:
    """Test setting each trim value."""
    setattr(mock_receiver, attribute, 0.0)

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: entity_id,
            "value": -6.0,
        },
        blocking=True,
    )

    assert getattr(mock_receiver, attribute) == -6.0


async def test_number_none_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test number entities show unknown when receiver values are None."""
    state = hass.states.get(LIPSYNC_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get(TRIM_BASS_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_receiver")
async def test_entities_absent_for_controls_the_model_lacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test no entity is created where the model has no such control.

    Absence alone would also be produced by an entity that was created and
    then failed, so this checks the setup stayed clean too.
    """
    mock_receiver.lipsync_range = None
    mock_receiver.trim_surround_range = None
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lyngdorf.lookup_receiver_model",
        return_value=LyngdorfModel.MP_60,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(LIPSYNC_ENTITY_ID) is None
    assert hass.states.get(TRIM_SURROUND_ENTITY_ID) is None
    assert hass.states.get(TRIM_BASS_ENTITY_ID) is not None
    assert "Error adding entity" not in caplog.text
    assert "AssertionError" not in caplog.text
