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
    # 4 statistical sensors only - hourly prices available via service
    assert len(entity_registry.entities) == 4

    # Check that all expected statistical sensors exist
    expected_sensors = [
        "sensor.gpe_highest_price_today",
        "sensor.gpe_lowest_price_day",
        "sensor.gpe_lowest_price_night",
        "sensor.gpe_current_price",
    ]

    for entity_id in expected_sensors:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["unit_of_measurement"] == "€/kWh"


async def test_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test statistical sensor values from mocked API."""
    # Test statistical sensor values based on mock data
    # Mock data generates price = 0.20 + (hour * 0.01)

    # Test highest price (should be hour 23 with 0.43)
    state_highest = hass.states.get("sensor.gpe_highest_price_today")
    assert state_highest.state == "0.43"
    assert state_highest.attributes["highest_price_hour"] == 23

    # Test lowest price day (should be hour 6 with 0.26)
    state_lowest_day = hass.states.get("sensor.gpe_lowest_price_day")
    assert state_lowest_day.state == "0.26"
    assert state_lowest_day.attributes["lowest_price_hour"] == 6

    # Test lowest price night (should be hour 0 with 0.20)
    state_lowest_night = hass.states.get("sensor.gpe_lowest_price_night")
    assert state_lowest_night.state == "0.2"
    assert state_lowest_night.attributes["lowest_price_hour"] == 0

    # Test current price (depends on current hour in test environment)
    state_current = hass.states.get("sensor.gpe_current_price")
    assert state_current is not None
    assert state_current.state is not None


async def test_special_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the special sensors (highest, day lowest, night lowest, current price)."""
    # Get all entities for the config entry
    entity_registry = er.async_get(hass)
    _ = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)

    # Find the special sensors by their unique_id pattern
    # Collect special sensor entities
    highest_entity = None
    lowest_day_entity = None
    lowest_night_entity = None
    current_entity = None
    chart_entity = None

    for entry in entity_registry.entities.values():
        if "highest_price_today" in entry.unique_id:
            highest_entity = entry.entity_id
        elif "lowest_price_day" in entry.unique_id:
            lowest_day_entity = entry.entity_id
        elif "lowest_price_night" in entry.unique_id:
            lowest_night_entity = entry.entity_id
        elif "current_price" in entry.unique_id and "chart" not in entry.unique_id:
            current_entity = entry.entity_id
        elif "price_chart_24h" in entry.unique_id:
            chart_entity = entry.entity_id

    # Test highest price sensor
    assert highest_entity is not None
    highest_state = hass.states.get(highest_entity)
    assert highest_state is not None
    assert highest_state.state == "0.43"  # Price for hour 23 should be highest
    assert highest_state.attributes["highest_price_hour"] == 23

    # Test lowest price day sensor (6-18h)
    assert lowest_day_entity is not None
    lowest_day_state = hass.states.get(lowest_day_entity)
    assert lowest_day_state is not None
    # Day hours (6-17): should find lowest price in range 0.26-0.37
    assert lowest_day_state.state == "0.26"  # Price for hour 6 should be lowest in day
    assert lowest_day_state.attributes["lowest_price_hour"] == 6
    assert lowest_day_state.attributes["period"] == "day (06:00-18:00)"

    # Test lowest price night sensor (18-6h)
    assert lowest_night_entity is not None
    lowest_night_state = hass.states.get(lowest_night_entity)
    assert lowest_night_state is not None
    # Night hours (18-23, 0-5): should find lowest price, which is hour 0 with 0.2
    assert (
        lowest_night_state.state == "0.2"
    )  # Price for hour 0 should be lowest in night
    assert lowest_night_state.attributes["lowest_price_hour"] == 0
    assert lowest_night_state.attributes["period"] == "night (18:00-06:00)"

    # Test current price sensor
    assert current_entity is not None
    current_state = hass.states.get(current_entity)
    assert current_state is not None
    # Current price depends on current hour, so we just check it's not None
    assert current_state.state is not None

    # Test 24h chart sensor - REMOVED as requested to avoid database storage
    assert chart_entity is None  # Chart sensor should not exist anymore

    assert "current_hour" in current_state.attributes
