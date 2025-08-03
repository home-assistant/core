"""Test Green Planet Energy sensor."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_sensor_setup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor setup."""
    # 27 sensors: 24 hourly sensors + 3 special sensors (highest, lowest, current)
    assert len(entity_registry.entities) == 27

    # Check that all expected sensors exist
    for hour in range(24):
        entity_id = f"sensor.preis_{hour:02d}_00"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["hour"] == hour
        assert state.attributes["unit_of_measurement"] == "€/kWh"


async def test_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test sensor values from mocked API."""
    # Test some specific sensor values based on mock data
    # Mock data generates price = 0.20 + (hour * 0.01)

    state_00 = hass.states.get("sensor.preis_00_00")
    assert state_00.state == "0.2"  # Changed from "0.20" to "0.2"

    state_09 = hass.states.get("sensor.preis_09_00")
    assert state_09.state == "0.29"

    state_12 = hass.states.get("sensor.preis_12_00")
    assert state_12.state == "0.32"

    state_15 = hass.states.get("sensor.preis_15_00")
    assert state_15.state == "0.35"

    state_18 = hass.states.get("sensor.preis_18_00")
    assert state_18.state == "0.38"

    state_23 = hass.states.get("sensor.preis_23_00")
    assert state_23.state == "0.43"


async def test_special_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the special sensors (highest, lowest, current price)."""
    # Test highest price sensor - need to find the actual entity ID
    # Based on the test output, it should be something like sensor.green_planet_energy_..._highest_price_today

    # Get all entities for the config entry
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )

    # Find the special sensors by their unique_id pattern
    highest_entity = None
    lowest_entity = None
    current_entity = None

    for entry in entries:
        if "highest_price_today" in entry.unique_id:
            highest_entity = entry.entity_id
        elif "lowest_price_today" in entry.unique_id:
            lowest_entity = entry.entity_id
        elif "current_price" in entry.unique_id:
            current_entity = entry.entity_id

    # Test highest price sensor
    assert highest_entity is not None
    highest_state = hass.states.get(highest_entity)
    assert highest_state is not None
    assert highest_state.state == "0.43"  # Price for hour 23 should be highest
    assert highest_state.attributes["highest_price_hour"] == 23

    # Test lowest price sensor
    assert lowest_entity is not None
    lowest_state = hass.states.get(lowest_entity)
    assert lowest_state is not None
    assert lowest_state.state == "0.2"  # Price for hour 0 should be lowest
    assert lowest_state.attributes["lowest_price_hour"] == 0

    # Test current price sensor
    assert current_entity is not None
    current_state = hass.states.get(current_entity)
    assert current_state is not None
    # Current price depends on current hour, so we just check it's not None
    assert current_state.state is not None
    assert "current_hour" in current_state.attributes
