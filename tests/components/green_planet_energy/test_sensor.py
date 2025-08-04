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
    # 29 sensors: 24 hourly sensors + 5 special sensors (highest, lowest_day, lowest_night, current, chart_48h)
    assert len(entity_registry.entities) == 29

    # Check that all expected sensors exist
    for hour in range(24):
        entity_id = f"sensor.gpe_price_{hour:02d}"
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

    state_00 = hass.states.get("sensor.gpe_price_00")
    assert state_00.state == "0.2"  # Changed from "0.20" to "0.2"

    state_09 = hass.states.get("sensor.gpe_price_09")
    assert state_09.state == "0.29"

    state_12 = hass.states.get("sensor.gpe_price_12")
    assert state_12.state == "0.32"

    state_15 = hass.states.get("sensor.gpe_price_15")
    assert state_15.state == "0.35"

    state_18 = hass.states.get("sensor.gpe_price_18")
    assert state_18.state == "0.38"

    state_23 = hass.states.get("sensor.gpe_price_23")
    assert state_23.state == "0.43"


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

    # Test 24h chart sensor
    assert chart_entity is not None
    chart_state = hass.states.get(chart_entity)
    assert chart_state is not None
    # Chart sensor shows current price as value
    assert chart_state.state is not None
    # Check that chart_data attribute exists and has 24 data points
    assert "chart_data" in chart_state.attributes
    chart_data = chart_state.attributes["chart_data"]
    assert len(chart_data) == 24  # 24 hours from current time
    assert chart_state.attributes["data_points"] == 24
    # Check structure of first data point
    first_point = chart_data[0]
    assert "hour" in first_point
    assert "price" in first_point
    assert "datetime" in first_point
    assert "time_slot" in first_point
    assert "day" in first_point
    assert "current_hour" in current_state.attributes
