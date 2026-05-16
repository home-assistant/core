"""Test the ScorpionTrack binary sensor platform."""

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_vehicle_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test vehicle-level ScorpionTrack binary sensors."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.ab12_cde_ignition").state == "on"
    assert hass.states.get("binary_sensor.ab12_cde_location_stale").state == "on"


async def test_binary_sensors_do_not_expose_map_coordinates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Only the tracker should expose coordinates for the Home Assistant map."""
    await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "binary_sensor.ab12_cde_ignition",
        "binary_sensor.ab12_cde_location_stale",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert "latitude" not in state.attributes
        assert "longitude" not in state.attributes
