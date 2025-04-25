"""Test Matter sensors."""

from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize("node_fixture", ["flow_sensor"])
async def test_sensor_null_value(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test flow sensor."""
    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "0.0"

    set_node_attribute(matter_node, 1, 1028, 0, None)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "unknown"


@pytest.mark.parametrize("node_fixture", ["flow_sensor"])
async def test_flow_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test flow sensor."""
    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "0.0"

    set_node_attribute(matter_node, 1, 1028, 0, 20)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_flow_sensor_flow")
    assert state
    assert state.state == "2.0"


@pytest.mark.parametrize("node_fixture", ["humidity_sensor"])
async def test_humidity_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test humidity sensor."""
    state = hass.states.get("sensor.mock_humidity_sensor_humidity")
    assert state
    assert state.state == "0.0"

    set_node_attribute(matter_node, 1, 1029, 0, 4000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_humidity_sensor_humidity")
    assert state
    assert state.state == "40.0"


@pytest.mark.parametrize("node_fixture", ["light_sensor"])
async def test_light_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test light sensor."""
    state = hass.states.get("sensor.mock_light_sensor_illuminance")
    assert state
    assert state.state == "1.3"

    set_node_attribute(matter_node, 1, 1024, 0, 3000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_light_sensor_illuminance")
    assert state
    assert state.state == "2.0"


@pytest.mark.parametrize("node_fixture", ["temperature_sensor"])
async def test_temperature_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test temperature sensor."""
    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state
    assert state.state == "21.0"

    set_node_attribute(matter_node, 1, 1026, 0, 2500)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_temperature_sensor_temperature")
    assert state
    assert state.state == "25.0"


@pytest.mark.parametrize("node_fixture", ["eve_contact_sensor"])
async def test_battery_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test battery sensor."""
    entity_id = "sensor.eve_door_battery"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "100"

    set_node_attribute(matter_node, 1, 47, 12, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "50"

    entry = entity_registry.async_get(entity_id)

    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize("node_fixture", ["eve_contact_sensor"])
async def test_battery_sensor_voltage(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test battery voltage sensor."""
    entity_id = "sensor.eve_door_voltage"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "3.558"

    set_node_attribute(matter_node, 1, 47, 11, 4234)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "4.234"

    entry = entity_registry.async_get(entity_id)

    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


@pytest.mark.parametrize("node_fixture", ["smoke_detector"])
async def test_battery_sensor_description(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test battery replacement description sensor."""
    state = hass.states.get("sensor.smoke_sensor_battery_type")
    assert state
    assert state.state == "CR123A"

    set_node_attribute(matter_node, 1, 47, 19, "CR2032")
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.smoke_sensor_battery_type")
    assert state
    assert state.state == "CR2032"

    # case with a empty string to check if the attribute is indeed ignored
    set_node_attribute(matter_node, 1, 47, 19, "")
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.smoke_sensor_battery_type") is None


@pytest.mark.parametrize("node_fixture", ["eve_thermo"])
async def test_eve_thermo_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Eve Thermo."""
    # Valve position
    state = hass.states.get("sensor.eve_thermo_valve_position")
    assert state
    assert state.state == "10"

    set_node_attribute(matter_node, 1, 319486977, 319422488, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.eve_thermo_valve_position")
    assert state
    assert state.state == "0"

    # LocalTemperature
    state = hass.states.get("sensor.eve_thermo_temperature")
    assert state
    assert state.state == "21.0"

    set_node_attribute(matter_node, 1, 513, 0, 1800)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.eve_thermo_temperature")
    assert state
    assert state.state == "18.0"


@pytest.mark.parametrize("node_fixture", ["pressure_sensor"])
async def test_pressure_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test pressure sensor."""
    state = hass.states.get("sensor.mock_pressure_sensor_pressure")
    assert state
    assert state.state == "0.0"

    set_node_attribute(matter_node, 1, 1027, 0, 1010)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.mock_pressure_sensor_pressure")
    assert state
    assert state.state == "101.0"


@pytest.mark.parametrize("node_fixture", ["eve_weather_sensor"])
async def test_eve_weather_sensor_custom_cluster(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test weather sensor created from (Eve) custom cluster."""
    # pressure sensor on Eve custom cluster
    state = hass.states.get("sensor.eve_weather_pressure")
    assert state
    assert state.state == "1008.5"

    set_node_attribute(matter_node, 1, 319486977, 319422484, 800)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("sensor.eve_weather_pressure")
    assert state
    assert state.state == "800.0"


@pytest.mark.parametrize("node_fixture", ["air_quality_sensor"])
async def test_air_quality_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test air quality sensor."""
    # Carbon Dioxide
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_carbon_dioxide")
    assert state
    assert state.state == "678.0"

    set_node_attribute(matter_node, 1, 1037, 0, 789)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_carbon_dioxide")
    assert state
    assert state.state == "789.0"

    # PM1
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm1")
    assert state
    assert state.state == "3.0"

    set_node_attribute(matter_node, 1, 1068, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm1")
    assert state
    assert state.state == "50.0"

    # PM2.5
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm2_5")
    assert state
    assert state.state == "3.0"

    set_node_attribute(matter_node, 1, 1066, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm2_5")
    assert state
    assert state.state == "50.0"

    # PM10
    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm10")
    assert state
    assert state.state == "3.0"

    set_node_attribute(matter_node, 1, 1069, 0, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.lightfi_aq1_air_quality_sensor_pm10")
    assert state
    assert state.state == "50.0"


@pytest.mark.parametrize("node_fixture", ["silabs_dishwasher"])
async def test_operational_state_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Operational State sensor, using a dishwasher fixture."""
    # OperationalState Cluster / OperationalState attribute (1/96/4)
    state = hass.states.get("sensor.dishwasher_operational_state")
    assert state
    assert state.state == "stopped"
    assert state.attributes["options"] == [
        "stopped",
        "running",
        "paused",
        "error",
        "extra_state",
    ]

    set_node_attribute(matter_node, 1, 96, 4, 8)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.dishwasher_operational_state")
    assert state
    assert state.state == "extra_state"


@pytest.mark.parametrize("node_fixture", ["yandex_smart_socket"])
async def test_draft_electrical_measurement_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Draft Electrical Measurement cluster sensors, using Yandex Smart Socket fixture."""
    state = hass.states.get("sensor.yndx_00540_power")
    assert state
    assert state.state == "70.0"

    # AcPowerDivisor
    set_node_attribute(matter_node, 1, 2820, 1541, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.yndx_00540_power")
    assert state
    assert state.state == "unknown"

    # ActivePower
    set_node_attribute(matter_node, 1, 2820, 1291, None)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.yndx_00540_power")
    assert state
    assert state.state == "unknown"


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_list_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Matter List sensor."""
    # OperationalState Cluster / CurrentPhase attribute (1/96/1)
    state = hass.states.get("sensor.laundrywasher_current_phase")
    assert state
    assert state.state == "pre-soak"

    set_node_attribute(matter_node, 1, 96, 1, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.laundrywasher_current_phase")
    assert state
    assert state.state == "rinse"


@pytest.mark.parametrize("node_fixture", ["silabs_evse_charging"])
async def test_evse_sensor(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test evse sensors."""
    # EnergyEvseFaultState
    state = hass.states.get("sensor.evse_fault_state")
    assert state
    assert state.state == "no_error"

    set_node_attribute(matter_node, 1, 153, 2, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.evse_fault_state")
    assert state
    assert state.state == "over_current"

    # EnergyEvseCircuitCapacity
    state = hass.states.get("sensor.evse_circuit_capacity")
    assert state
    assert state.state == "32.0"

    set_node_attribute(matter_node, 1, 153, 5, 63000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.evse_circuit_capacity")
    assert state
    assert state.state == "63.0"

    # EnergyEvseMinimumChargeCurrent
    state = hass.states.get("sensor.evse_min_charge_current")
    assert state
    assert state.state == "2.0"

    set_node_attribute(matter_node, 1, 153, 6, 5000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.evse_min_charge_current")
    assert state
    assert state.state == "5.0"

    # EnergyEvseMaximumChargeCurrent
    state = hass.states.get("sensor.evse_max_charge_current")
    assert state
    assert state.state == "30.0"

    set_node_attribute(matter_node, 1, 153, 7, 20000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.evse_max_charge_current")
    assert state
    assert state.state == "20.0"

    # EnergyEvseUserMaximumChargeCurrent
    state = hass.states.get("sensor.evse_user_max_charge_current")
    assert state
    assert state.state == "32.0"

    set_node_attribute(matter_node, 1, 153, 9, 63000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.evse_user_max_charge_current")
    assert state
    assert state.state == "63.0"


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water heater sensor."""
    # TankVolume
    state = hass.states.get("sensor.water_heater_tank_volume")
    assert state
    assert state.state == "200"

    set_node_attribute(matter_node, 2, 148, 2, 100)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.water_heater_tank_volume")
    assert state
    assert state.state == "100"

    # EstimatedHeatRequired
    state = hass.states.get("sensor.water_heater_required_heating_energy")
    assert state
    assert state.state == "4.0"

    set_node_attribute(matter_node, 2, 148, 3, 1000000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.water_heater_required_heating_energy")
    assert state
    assert state.state == "1.0"

    # TankPercentage
    state = hass.states.get("sensor.water_heater_hot_water_level")
    assert state
    assert state.state == "40"

    set_node_attribute(matter_node, 2, 148, 4, 50)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("sensor.water_heater_hot_water_level")
    assert state
    assert state.state == "50"
