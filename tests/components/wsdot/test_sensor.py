"""The tests for the WSDOT platform."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant


async def test_travel_sensor_details(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_data: dict,
    sync_sensor,
) -> None:
    """Test the wsdot Travel Time sensor details."""
    state = hass.states.get("sensor.i90_eb")
    assert state is not None
    assert state.name == "I90 EB"
    assert state.state == "11"
    assert (
        state.attributes["Description"]
        == "Downtown Seattle to Downtown Bellevue via I-90"
    )
    assert state.attributes["TimeUpdated"] == datetime(
        2017, 1, 21, 15, 10, tzinfo=timezone(timedelta(hours=-8))
    )
