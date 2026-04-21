"""Test the ScorpionTrack device tracker platform."""

from dataclasses import replace

from pyscorpiontrack import ScorpionTrackShare

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_tracker_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the ScorpionTrack device tracker state and attributes."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.ab12_cde")
    assert state is not None
    assert state.state == "not_home"
    assert state.attributes["latitude"] == 51.5074
    assert state.attributes["longitude"] == -0.1278
    assert state.attributes["gps_accuracy"] == 0.0
    assert state.attributes["source_type"] == "gps"
    assert state.attributes["address"] == "Westminster, London"
    assert state.attributes["speed"] == 30.0
    assert state.attributes["speed_unit"] == "mph"

    entity_entry = entity_registry.async_get("device_tracker.ab12_cde")
    assert entity_entry is not None
    assert entity_entry.original_name == "AB12 CDE"


async def test_device_is_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the ScorpionTrack vehicle device is registered."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={("scorpiontrack", "101_1")})
    assert device is not None
    assert device.name == "AB12 CDE"
    assert device.manufacturer == "Volkswagen"
    assert device.model == "Golf R"


async def test_removed_vehicle_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
) -> None:
    """Test a tracker becomes unavailable if its vehicle leaves the share."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    coordinator.async_set_updated_data(replace(mock_share, vehicles=()))
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.ab12_cde")
    assert state is not None
    assert state.state == "unavailable"

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={("scorpiontrack", "101_1")})
    assert device is not None
    assert device.name == "AB12 CDE"
