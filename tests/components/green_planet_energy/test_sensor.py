"""Test the Green Planet Energy sensor platform."""

from homeassistant.components.green_planet_energy.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant, mock_api, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor platform."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="green_planet_energy",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that all hour sensors are created
    for hour in range(9, 19):
        entity_id = f"sensor.preis_{hour:02d}_00"
        state = hass.states.get(entity_id)
        assert state is not None

        # Check the sensor attributes
        assert state.attributes["hour"] == hour
        assert state.attributes["time_slot"] == f"{hour:02d}:00-{hour + 1:02d}:00"

        # Check entity registry entry
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.unique_id == f"{config_entry.entry_id}_price_{hour:02d}"


async def test_sensor_values(hass: HomeAssistant, mock_api) -> None:
    """Test sensor values from mocked API."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id="green_planet_energy",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test some specific sensor values based on mock data
    state_09 = hass.states.get("sensor.preis_09_00")
    assert state_09.state == "0.25"

    state_12 = hass.states.get("sensor.preis_12_00")
    assert state_12.state == "0.32"

    state_18 = hass.states.get("sensor.preis_18_00")
    assert state_18.state == "0.3"
