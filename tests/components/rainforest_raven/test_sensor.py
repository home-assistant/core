"""Tests for the Rainforest RAVEn sensors."""

import pytest

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_entry")
async def test_sensors(hass: HomeAssistant) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 5

    demand = hass.states.get("sensor.raven_device_meter_power_demand")
    assert demand is not None
    assert demand.state == "1.2345"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.raven_device_total_meter_energy_delivered")
    assert delivered is not None
    assert delivered.state == "23456.7890"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.raven_device_total_meter_energy_received")
    assert received is not None
    assert received.state == "00000.0000"
    assert received.attributes["unit_of_measurement"] == "kWh"

    price = hass.states.get("sensor.raven_device_meter_price")
    assert price is not None
    assert price.state == "0.10"
    assert price.attributes["unit_of_measurement"] == "USD/kWh"

    signal = hass.states.get("sensor.raven_device_meter_signal_strength")
    assert signal is not None
    assert signal.state == "100"
    assert signal.attributes["unit_of_measurement"] == "%"
