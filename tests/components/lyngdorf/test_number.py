"""Tests for the Lyngdorf number platform."""

from unittest.mock import MagicMock, patch

from lyngdorf import LyngdorfModel, Trim
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import notify_receiver_update

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the number platform."""
    return [Platform.NUMBER]


LIPSYNC_ENTITY_ID = "number.mock_lyngdorf_lip_sync"
TRIM_BASS_ENTITY_ID = "number.mock_lyngdorf_trim_bass"
TRIM_TREBLE_ENTITY_ID = "number.mock_lyngdorf_trim_treble"
TRIM_CENTRE_ENTITY_ID = "number.mock_lyngdorf_trim_centre"
TRIM_HEIGHT_ENTITY_ID = "number.mock_lyngdorf_trim_height"
TRIM_LFE_ENTITY_ID = "number.mock_lyngdorf_trim_lfe"
TRIM_SURROUND_ENTITY_ID = "number.mock_lyngdorf_trim_surround"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the number entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_set_lipsync(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test setting the lipsync value."""
    mock_receiver.lipsync.value = 0

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: LIPSYNC_ENTITY_ID,
            ATTR_VALUE: 75,
        },
        blocking=True,
    )

    mock_receiver.lipsync.set.assert_awaited_once_with(75)


@pytest.mark.parametrize(
    ("entity_id", "trim"),
    [
        pytest.param(TRIM_BASS_ENTITY_ID, Trim.BASS, id="bass"),
        pytest.param(TRIM_TREBLE_ENTITY_ID, Trim.TREBLE, id="treble"),
        pytest.param(TRIM_CENTRE_ENTITY_ID, Trim.CENTER, id="centre"),
        pytest.param(TRIM_HEIGHT_ENTITY_ID, Trim.HEIGHT, id="height"),
        pytest.param(TRIM_LFE_ENTITY_ID, Trim.LFE, id="lfe"),
        pytest.param(TRIM_SURROUND_ENTITY_ID, Trim.SURROUND, id="surround"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_set_trim(
    hass: HomeAssistant,
    mock_receiver: MagicMock,
    entity_id: str,
    trim: Trim,
) -> None:
    """Test setting each trim value."""
    mock_receiver.trims[trim].value = 0.0

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: -6.0,
        },
        blocking=True,
    )

    mock_receiver.trims[trim].set.assert_awaited_once_with(-6.0)


async def test_number_none_values(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test a number shows unknown when the device reports nothing."""
    mock_receiver.lipsync = None
    mock_receiver.trims[Trim.BASS].value = None
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    assert hass.states.get(LIPSYNC_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(TRIM_BASS_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_created_before_the_device_reports_a_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test a control the model has still gets an entity before its first report."""
    mock_receiver.lipsync = None
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lyngdorf.lookup_model",
            return_value=LyngdorfModel.MP_60,
        ),
        patch("homeassistant.components.lyngdorf.PLATFORMS", [Platform.NUMBER]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(LIPSYNC_ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_receiver")
async def test_entities_absent_for_controls_the_model_lacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test no entity is created where the model has no such control."""
    mock_receiver.lipsync_range = None
    del mock_receiver.trims[Trim.SURROUND]
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lyngdorf.lookup_model",
            return_value=LyngdorfModel.MP_60,
        ),
        patch("homeassistant.components.lyngdorf.PLATFORMS", [Platform.NUMBER]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(LIPSYNC_ENTITY_ID) is None
    assert hass.states.get(TRIM_SURROUND_ENTITY_ID) is None
    assert hass.states.get(TRIM_BASS_ENTITY_ID) is not None


@pytest.mark.usefixtures("init_integration")
async def test_channel_trims_disabled_by_default(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only the commonly used trims are enabled by default."""
    for entity_id in (LIPSYNC_ENTITY_ID, TRIM_BASS_ENTITY_ID, TRIM_TREBLE_ENTITY_ID):
        assert entity_registry.async_get(entity_id).disabled_by is None

    for entity_id in (
        TRIM_CENTRE_ENTITY_ID,
        TRIM_HEIGHT_ENTITY_ID,
        TRIM_LFE_ENTITY_ID,
        TRIM_SURROUND_ENTITY_ID,
    ):
        entry = entity_registry.async_get(entity_id)
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
