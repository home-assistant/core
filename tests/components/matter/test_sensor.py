"""Test Matter sensors."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="flow_sensor_node")
async def flow_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a flow sensor node."""
    return await setup_integration_with_node_fixture(hass, "flow-sensor", matter_client)


@pytest.fixture(name="humidity_sensor_node")
async def humidity_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a humidity sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "humidity-sensor", matter_client
    )


@pytest.fixture(name="light_sensor_node")
async def light_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a light sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "light-sensor", matter_client
    )


@pytest.fixture(name="pressure_sensor_node")
async def pressure_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a pressure sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "pressure-sensor", matter_client
    )


@pytest.fixture(name="temperature_sensor_node")
async def temperature_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a temperature sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "temperature-sensor", matter_client
    )


@pytest.fixture(name="eve_energy_plug_node")
async def eve_energy_plug_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Eve Energy Plug node."""
    return await setup_integration_with_node_fixture(
        hass, "eve-energy-plug", matter_client
    )


@pytest.fixture(name="air_quality_sensor_node")
async def air_quality_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an air quality sensor (LightFi AQ1) node."""
    return await setup_integration_with_node_fixture(
        hass, "air-quality-sensor", matter_client
    )


@pytest.fixture(name="air_purifier_node")
async def air_purifier_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an air purifier node."""
    return await setup_integration_with_node_fixture(
        hass, "air-purifier", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_sensor_null_value(
    hass: HomeAssistant,
    matter_client: MagicMock,
    flow_sensor_node: MatterNode,
) -> None:
    """Test flow sensor."""
    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "0.0"

    set_node_attribute(flow_sensor_node, 1, 1028, 0, None)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "unknown"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_flow_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    flow_sensor_node: MatterNode,
) -> None:
    """Test flow sensor."""
    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "0.0"

    set_node_attribute(flow_sensor_node, 1, 1028, 0, 20)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "2.0"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_humidity_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    humidity_sensor_node: MatterNode,
) -> None:
    """Test humidity sensor."""
    state = hass.states.get("sensor.mock_humidity_sensor_humidity")
    assert state
    assert state.state == "0.0"

    set_node_attribute(humidity_sensor_node, 1, 1029, 0, 4000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_humidity_sensor_humidity")
    assert state
    assert state.state == "40.0"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_light_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_sensor_node: MatterNode,
) -> None:
    """Test light sensor."""
    state = hass.states.get("sensor.mock_light_sensor_illuminance")
    assert state
    assert state.state == "1.3"

    set_node_attribute(light_sensor_node, 1, 1024, 0, 3000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_light_sensor_illuminance")
    assert state
    assert state.state == "2.0"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_pressure_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    pressure_sensor_node: MatterNode,
) -> None:
    """Test pressure sensor."""
    state = hass.states.get("sensor.mock_pressure_sensor_pressure")
    assert state
    assert state.state == "0.0"

    set_node_attribute(pressure_sensor_node, 1, 1027, 0, 1010)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_pressure_sensor_pressure")
    assert state
    assert state.state == "101.0"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_temperature_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    temperature_sensor_node: MatterNode,
) -> None:
    """Test temperature sensor."""
    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state
    assert state.state == "21.0"

    set_node_attribute(temperature_sensor_node, 1, 1026, 0, 2500)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state
    assert state.state == "25.0"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_battery_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    eve_contact_sensor_node: MatterNode,
) -> None:
    """Test battery sensor."""
    entity_id = "sensor.eve_door_battery"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "100"

    set_node_attribute(eve_contact_sensor_node, 1, 47, 12, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "50"

    entry = entity_registry.async_get(entity_id)

    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_eve_energy_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    eve_energy_plug_node: MatterNode,
) -> None:
    """Test Energy sensors created from Eve Energy custom cluster."""
    # power sensor
    entity_id = "sensor.eve_energy_plug_power"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == "power"
    assert state.attributes["friendly_name"] == "Eve Energy Plug Power"

    # voltage sensor
    entity_id = "sensor.eve_energy_plug_voltage"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "238.800003051758"
    assert state.attributes["unit_of_measurement"] == "V"
    assert state.attributes["device_class"] == "voltage"
    assert state.attributes["friendly_name"] == "Eve Energy Plug Voltage"

    # energy sensor
    entity_id = "sensor.eve_energy_plug_energy"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.220000028610229"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["friendly_name"] == "Eve Energy Plug Energy"
    assert state.attributes["state_class"] == "total_increasing"

    # current sensor
    entity_id = "sensor.eve_energy_plug_current"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == "A"
    assert state.attributes["device_class"] == "current"
    assert state.attributes["friendly_name"] == "Eve Energy Plug Current"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_air_quality_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    air_quality_sensor_node: MatterNode,
) -> None:
    """Test air quality sensor."""
    # Carbon Dioxide
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_carbon_dioxide")
    assert state
    assert state.state == "678.0"

    set_node_attribute(air_quality_sensor_node, 1, 1037, 0, 789)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_carbon_dioxide")
    assert state
    assert state.state == "789.0"

    # PM1
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm1")
    assert state
    assert state.state == "3.0"

    set_node_attribute(air_quality_sensor_node, 1, 1068, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm1")
    assert state
    assert state.state == "50.0"

    # PM2.5
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm2_5")
    assert state
    assert state.state == "3.0"

    set_node_attribute(air_quality_sensor_node, 1, 1066, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm2_5")
    assert state
    assert state.state == "50.0"

    # PM10
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm10")
    assert state
    assert state.state == "3.0"

    set_node_attribute(air_quality_sensor_node, 1, 1069, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm10")
    assert state
    assert state.state == "50.0"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_air_purifier_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    air_purifier_node: MatterNode,
) -> None:
    """Test Air quality sensors are creayted for air purifier device."""
    # Carbon Dioxide
    state = hass.states.get("sensor.air_purifier_carbon_dioxide")
    assert state
    assert state.state == "2.0"

    # PM1
    state = hass.states.get("sensor.air_purifier_pm1")
    assert state
    assert state.state == "2.0"

    # PM2.5
    state = hass.states.get("sensor.air_purifier_pm2_5")
    assert state
    assert state.state == "2.0"

    # PM10
    state = hass.states.get("sensor.air_purifier_pm10")
    assert state
    assert state.state == "2.0"

    # Temperature
    state = hass.states.get("sensor.air_purifier_temperature")
    assert state
    assert state.state == "20.0"

    # Humidity
    state = hass.states.get("sensor.air_purifier_humidity")
    assert state
    assert state.state == "50.0"

    # VOCS
    state = hass.states.get("sensor.air_purifier_vocs")
    assert state
    assert state.state == "2.0"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "ppm"
    assert state.attributes["device_class"] == "volatile_organic_compounds_parts"
    assert state.attributes["friendly_name"] == "Air Purifier VOCs"

    # Air Quality
    state = hass.states.get("sensor.air_purifier_air_quality")
    assert state
    assert state.state == "good"
    expected_options = [
        "extremely_poor",
        "very_poor",
        "poor",
        "fair",
        "good",
        "moderate",
        "unknown",
    ]
    assert set(state.attributes["options"]) == set(expected_options)
    assert state.attributes["device_class"] == "enum"
    assert state.attributes["friendly_name"] == "Air Purifier Air quality"

    # Carbon MonoOxide
    state = hass.states.get("sensor.air_purifier_carbon_monoxide")
    assert state
    assert state.state == "2.0"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "ppm"
    assert state.attributes["device_class"] == "carbon_monoxide"
    assert state.attributes["friendly_name"] == "Air Purifier Carbon monoxide"

    # Nitrogen Dioxide
    state = hass.states.get("sensor.air_purifier_nitrogen_dioxide")
    assert state
    assert state.state == "2.0"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "ppm"
    assert state.attributes["device_class"] == "nitrogen_dioxide"
    assert state.attributes["friendly_name"] == "Air Purifier Nitrogen dioxide"

    # Ozone Concentration
    state = hass.states.get("sensor.air_purifier_ozone")
    assert state
    assert state.state == "2.0"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "ppm"
    assert state.attributes["device_class"] == "ozone"
    assert state.attributes["friendly_name"] == "Air Purifier Ozone"

    # Hepa Filter Condition
    state = hass.states.get("sensor.air_purifier_hepa_filter_condition")
    assert state
    assert state.state == "100"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["friendly_name"] == "Air Purifier Hepa filter condition"

    # Activated Carbon Filter Condition
    state = hass.states.get("sensor.air_purifier_activated_carbon_filter_condition")
    assert state
    assert state.state == "100"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "%"
