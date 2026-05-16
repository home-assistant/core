"""Test the ScorpionTrack sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock

from pyscorpiontrack import ScorpionTrackShare

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_vehicle_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test vehicle-level ScorpionTrack sensors."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.ab12_cde_status").state == "Moving"
    assert hass.states.get("sensor.ab12_cde_location").state == "Westminster, London"

    speed = hass.states.get("sensor.ab12_cde_speed")
    assert speed.state == "30.0"
    assert speed.attributes["unit_of_measurement"] == "mph"

    assert hass.states.get("sensor.ab12_cde_heading").state == "182"
    assert hass.states.get("sensor.ab12_cde_last_reported").state != "unknown"


async def test_speed_sensor_handles_missing_speed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """The speed sensor should be unknown when the shared position has no speed."""
    vehicle = mock_share.vehicles[0]
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share,
        vehicles=(
            replace(vehicle, position=replace(vehicle.position, speed_kmh=None)),
        ),
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.ab12_cde_speed").state == "unknown"


async def test_share_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test share-level ScorpionTrack sensors."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.family_cars_share_title").state == "Family Cars"
    assert hass.states.get("sensor.family_cars_shared_by").state == "Ashby Herbert"
    assert hass.states.get("sensor.family_cars_share_created").state != "unknown"
    assert hass.states.get("sensor.family_cars_share_expires").state != "unknown"


async def test_sensors_do_not_expose_map_coordinates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Only the tracker should expose coordinates for the Home Assistant map."""
    await setup_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.ab12_cde_status",
        "sensor.ab12_cde_location",
        "sensor.ab12_cde_speed",
        "sensor.ab12_cde_heading",
        "sensor.ab12_cde_last_reported",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert "latitude" not in state.attributes
        assert "longitude" not in state.attributes
