"""Tests for Arcam FMJ binary sensor entities."""

from unittest.mock import Mock

from arcam.fmj import ConnectionFailed
import pytest

from homeassistant.components.arcam_fmj.const import (
    SIGNAL_CLIENT_DATA,
    SIGNAL_CLIENT_STARTED,
    SIGNAL_CLIENT_STOPPED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import MOCK_HOST, MOCK_UUID


def _get_entity_id(entity_registry: er.EntityRegistry, zone: int) -> str:
    """Get entity_id for the interlaced binary sensor by unique_id."""
    unique_id = f"{MOCK_UUID}-{zone}-incoming_video_interlaced"
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "arcam_fmj", unique_id
    )
    assert entity_id is not None, f"Missing binary sensor: zone {zone}"
    return entity_id


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensors_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that binary sensor entities are created for both zones."""
    for zone in (1, 2):
        entity_id = _get_entity_id(entity_registry, zone)
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is not None


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_interlaced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor value for interlaced video."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_not_interlaced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor value for progressive video."""
    video_params = Mock()
    video_params.interlaced = False
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor when video parameters are None."""
    state_1.get_incoming_video_parameters.return_value = None

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_connection_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test binary sensor handles ConnectionFailed during setup."""
    state_1.update.side_effect = ConnectionFailed()

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert "Connection lost during addition" in caplog.text


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_signal_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor updates on data signal."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Change value and send data signal
    video_params.interlaced = False
    async_dispatcher_send(hass, SIGNAL_CLIENT_DATA, MOCK_HOST)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_signal_data_wrong_host(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor ignores data signal from different host."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Change value but send signal for wrong host
    video_params.interlaced = False
    async_dispatcher_send(hass, SIGNAL_CLIENT_DATA, "wrong_host")
    await hass.async_block_till_done()

    # State should not have changed
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_signal_stopped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor becomes unavailable on stopped signal."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    async_dispatcher_send(hass, SIGNAL_CLIENT_STOPPED, MOCK_HOST)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_signal_started(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor becomes available on started signal."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # First make it unavailable
    async_dispatcher_send(hass, SIGNAL_CLIENT_STOPPED, MOCK_HOST)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"

    # Then bring it back
    async_dispatcher_send(hass, SIGNAL_CLIENT_STARTED, MOCK_HOST)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"
