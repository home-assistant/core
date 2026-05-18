"""Test the ScorpionTrack device tracker platform."""

from dataclasses import replace

from pyscorpiontrack import ScorpionTrackShare

from homeassistant.components.scorpiontrack.device_tracker import (
    ScorpionTrackTrackerEntity,
)
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
    assert "address" not in state.attributes
    assert "speed" not in state.attributes
    assert "speed_unit" not in state.attributes

    entity_entry = entity_registry.async_get("device_tracker.ab12_cde")
    assert entity_entry is not None
    assert entity_entry.unique_id == "101_1"


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


async def test_new_vehicles_after_setup_do_not_add_tracker_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
) -> None:
    """Vehicles that appear later should wait for a future dynamic-device PR."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    new_vehicle = replace(
        mock_share.vehicles[0],
        id=2,
        name="Tiguan",
        registration="EF34 ABC",
        model="Tiguan",
    )
    coordinator.async_set_updated_data(
        replace(mock_share, vehicles=(*mock_share.vehicles, new_vehicle))
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.ef34_abc") is None


async def test_tracker_uses_device_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The tracker should use the vehicle device name as the main entity name."""
    await setup_integration(hass, mock_config_entry)

    entity = ScorpionTrackTrackerEntity(mock_config_entry.runtime_data, 1)

    assert entity.has_entity_name is True
    assert entity.name is None
