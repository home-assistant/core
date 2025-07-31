"""The sensor tests for the tado platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def loaded_platforms():
    """Load the binary sensor platform for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SENSOR]):
        yield


async def trigger_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an update of the Tado integration.

    Since the binary sensor platform doesn't infer a state immediately without extra requests,
    so adding this here to remove in a follow-up PR.
    """
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_tado_api")
async def test_air_con_create_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of aircon sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("sensor.air_conditioning_tado_mode")
    assert state.state == "HOME"

    state = hass.states.get("sensor.air_conditioning_temperature")
    assert state.state == "24.76"

    state = hass.states.get("sensor.air_conditioning_ac")
    assert state.state == "ON"

    state = hass.states.get("sensor.air_conditioning_humidity")
    assert state.state == "60.9"


@pytest.mark.usefixtures("mock_tado_api")
async def test_home_create_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of home sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("sensor.home_name_outdoor_temperature")
    assert state.state == "7.46"

    state = hass.states.get("sensor.home_name_solar_percentage")
    assert state.state == "2.1"

    state = hass.states.get("sensor.home_name_weather_condition")
    assert state.state == "fog"


@pytest.mark.usefixtures("mock_tado_api")
async def test_heater_create_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of heater sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("sensor.baseboard_heater_tado_mode")
    assert state.state == "HOME"

    state = hass.states.get("sensor.baseboard_heater_temperature")
    assert state.state == "20.65"

    state = hass.states.get("sensor.baseboard_heater_humidity")
    assert state.state == "45.2"


@pytest.mark.usefixtures("mock_tado_api")
async def test_water_heater_create_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of water heater sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("sensor.water_heater_tado_mode")
    assert state.state == "HOME"
