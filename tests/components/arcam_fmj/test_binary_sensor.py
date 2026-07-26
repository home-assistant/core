"""Tests for Arcam FMJ binary sensor entities."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from arcam.fmj.state import State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Limit platform setup to binary_sensor only."""
    with patch(
        "homeassistant.components.arcam_fmj.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the binary sensor platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_none(
    hass: HomeAssistant,
) -> None:
    """Test binary sensor when video parameters are None."""
    state = hass.states.get(
        "binary_sensor.arcam_fmj_127_0_0_1_incoming_video_interlaced"
    )
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_interlaced(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test binary sensor reports on when video is interlaced."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.arcam_fmj_127_0_0_1_incoming_video_interlaced"
    )
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_not_interlaced(
    hass: HomeAssistant,
    state_1: State,
    client: Mock,
) -> None:
    """Test binary sensor reports off when video is not interlaced."""
    video_params = Mock()
    video_params.interlaced = False
    state_1.get_incoming_video_parameters.return_value = video_params

    client.notify_data_updated()
    await hass.async_block_till_done()

    state = hass.states.get(
        "binary_sensor.arcam_fmj_127_0_0_1_incoming_video_interlaced"
    )
    assert state is not None
    assert state.state == STATE_OFF
