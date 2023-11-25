"""Test Hydrawise binary_sensor."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.hydrawise.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_states(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary_sensor states."""
    connectivity = hass.states.get("binary_sensor.home_controller_connectivity")
    assert connectivity is not None
    assert connectivity.state == "on"

    watering1 = hass.states.get("binary_sensor.zone_one_watering")
    assert watering1 is not None
    assert watering1.state == "off"

    watering2 = hass.states.get("binary_sensor.zone_two_watering")
    assert watering2 is not None
    assert watering2.state == "on"


async def test_update_data_fails(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that no data from the API sets the correct connectivity."""
    # Make the coordinator refresh data.
    mock_pydrawise.get_user.reset_mock(return_value=True)
    mock_pydrawise.get_user.side_effect = ClientError
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    connectivity = hass.states.get("binary_sensor.home_controller_connectivity")
    assert connectivity is not None
    assert connectivity.state == "unavailable"
