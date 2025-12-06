"""PurpleAir sensors tests."""

from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest

from homeassistant.components.sensor import UnitOfTemperature
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant


async def test_sensor_values(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """Test sensor values."""

    state = hass.states.get("sensor.test_sensor_temperature")
    assert state
    assert state.state == "27.7777777777778"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "get_sensors_mock",
    [
        AsyncMock(side_effect=Exception),
        AsyncMock(side_effect=PurpleAirError),
        AsyncMock(side_effect=InvalidApiKeyError),
    ],
)
async def test_sensor_values_error(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    mock_aiopurpleair,
    api,
    get_sensors_mock,
) -> None:
    """Test sensor values."""

    with patch.object(api.sensors, "async_get_sensors", get_sensors_mock):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is None

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
