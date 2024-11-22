"""Tests for rainforest eagle sensors."""

from homeassistant.components.rainforest_eagle.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_200_RESPONSE_WITH_PRICE


async def test_sensors_200(hass: HomeAssistant, setup_rainforest_200) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 3

    demand = hass.states.get("sensor.eagle_200_meter_power_demand")
    assert demand is not None
    assert demand.state == "1.152000"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.eagle_200_total_meter_energy_delivered")
    assert delivered is not None
    assert delivered.state == "45251.285000"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.eagle_200_total_meter_energy_received")
    assert received is not None
    assert received.state == "232.232000"
    assert received.attributes["unit_of_measurement"] == "kWh"

    setup_rainforest_200.get_device_query.return_value = MOCK_200_RESPONSE_WITH_PRICE

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 4

    price = hass.states.get("sensor.eagle_200_meter_price")
    assert price is not None
    assert price.state == "0.053990"
    assert price.attributes["unit_of_measurement"] == "USD/kWh"


async def test_sensors_100(hass: HomeAssistant, setup_rainforest_100) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 3

    demand = hass.states.get("sensor.eagle_100_meter_power_demand")
    assert demand is not None
    assert demand.state == "1.152000"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.eagle_100_total_meter_energy_delivered")
    assert delivered is not None
    assert delivered.state == "45251.285000"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.eagle_100_total_meter_energy_received")
    assert received is not None
    assert received.state == "232.232000"
    assert received.attributes["unit_of_measurement"] == "kWh"
