"""The sensor tests for the tado platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def loaded_platforms():
    """Load the binary sensor platform for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.BINARY_SENSOR]):
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
async def test_air_con_create_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of aircon sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("binary_sensor.air_conditioning_power")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.air_conditioning_connectivity")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.air_conditioning_overlay")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.air_conditioning_window")
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_tado_api")
async def test_heater_create_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of heater sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("binary_sensor.baseboard_heater_power")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.baseboard_heater_connectivity")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.baseboard_heater_early_start")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.baseboard_heater_overlay")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.baseboard_heater_window")
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_tado_api")
async def test_water_heater_create_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of water heater sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("binary_sensor.water_heater_connectivity")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.water_heater_overlay")
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.water_heater_power")
    assert state.state == STATE_ON


@pytest.mark.usefixtures("mock_tado_api")
async def test_home_create_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creation of home binary sensors."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    state = hass.states.get("binary_sensor.wr1_connection_state")
    assert state.state == STATE_ON
