"""Tests for rainforest eagle sensors."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_100,
    TYPE_EAGLE_200,
)
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CLOUD_ID = "12345"
MOCK_200_RESPONSE_WITH_PRICE = {
    "zigbee:InstantaneousDemand": {
        "Name": "zigbee:InstantaneousDemand",
        "Value": "1.152000",
    },
    "zigbee:CurrentSummationDelivered": {
        "Name": "zigbee:CurrentSummationDelivered",
        "Value": "45251.285000",
    },
    "zigbee:CurrentSummationReceived": {
        "Name": "zigbee:CurrentSummationReceived",
        "Value": "232.232000",
    },
    "zigbee:Price": {"Name": "zigbee:Price", "Value": "0.053990"},
    "zigbee:PriceCurrency": {"Name": "zigbee:PriceCurrency", "Value": "USD"},
}
MOCK_200_RESPONSE_WITHOUT_PRICE = {
    "zigbee:InstantaneousDemand": {
        "Name": "zigbee:InstantaneousDemand",
        "Value": "1.152000",
    },
    "zigbee:CurrentSummationDelivered": {
        "Name": "zigbee:CurrentSummationDelivered",
        "Value": "45251.285000",
    },
    "zigbee:CurrentSummationReceived": {
        "Name": "zigbee:CurrentSummationReceived",
        "Value": "232.232000",
    },
    "zigbee:Price": {"Name": "zigbee:Price", "Value": "invalid"},
    "zigbee:PriceCurrency": {"Name": "zigbee:PriceCurrency", "Value": "USD"},
}


@pytest.fixture
async def setup_rainforest_200(hass):
    """Set up rainforest."""
    MockConfigEntry(
        domain="rainforest_eagle",
        data={
            CONF_CLOUD_ID: MOCK_CLOUD_ID,
            CONF_HOST: "192.168.1.55",
            CONF_INSTALL_CODE: "abcdefgh",
            CONF_HARDWARE_ADDRESS: "mock-hw-address",
            CONF_TYPE: TYPE_EAGLE_200,
        },
    ).add_to_hass(hass)
    with patch(
        "aioeagle.ElectricMeter.create_instance",
        return_value=Mock(
            get_device_query=AsyncMock(return_value=MOCK_200_RESPONSE_WITHOUT_PRICE)
        ),
    ) as mock_update:
        mock_update.return_value.is_connected = True
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update.return_value


@pytest.fixture
async def setup_rainforest_100(hass):
    """Set up rainforest."""
    MockConfigEntry(
        domain="rainforest_eagle",
        data={
            CONF_CLOUD_ID: MOCK_CLOUD_ID,
            CONF_HOST: "192.168.1.55",
            CONF_INSTALL_CODE: "abcdefgh",
            CONF_HARDWARE_ADDRESS: None,
            CONF_TYPE: TYPE_EAGLE_100,
        },
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_eagle.data.Eagle100Reader",
        return_value=Mock(
            get_instantaneous_demand=Mock(
                return_value={"InstantaneousDemand": {"Demand": "1.152000"}}
            ),
            get_current_summation=Mock(
                return_value={
                    "CurrentSummation": {
                        "SummationDelivered": "45251.285000",
                        "SummationReceived": "232.232000",
                    }
                }
            ),
        ),
    ) as mock_update:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update


async def test_sensors_200(hass, setup_rainforest_200):
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

    price = hass.states.get("sensor.meter_price")
    assert price is not None
    assert price.state == "0.053990"
    assert price.attributes["unit_of_measurement"] == "USD/kWh"


async def test_sensors_100(hass, setup_rainforest_100):
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
