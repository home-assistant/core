"""Tests for rainforest eagle sensors."""
from unittest.mock import patch

import pytest

from homeassistant.components.rainforest_eagle.const import (
    CONF_CLOUD_ID,
    CONF_HARDWARE_ADDRESS,
    CONF_INSTALL_CODE,
    DOMAIN,
    TYPE_EAGLE_100,
    TYPE_EAGLE_200,
)
from homeassistant.const import CONF_TYPE
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CLOUD_ID = "12345"
MOCK_200_RESPONSE_WITH_PRICE = {
    "zigbee:InstantaneousDemand": "1.152000",
    "zigbee:CurrentSummationDelivered": "45251.285000",
    "zigbee:CurrentSummationReceived": "232.232000",
    "zigbee:Price": "0.053990",
    "zigbee:PriceCurrency": "USD",
}
MOCK_200_RESPONSE_WITHOUT_PRICE = {
    "zigbee:InstantaneousDemand": "1.152000",
    "zigbee:CurrentSummationDelivered": "45251.285000",
    "zigbee:CurrentSummationReceived": "232.232000",
    "zigbee:Price": "invalid",
    "zigbee:PriceCurrency": "USD",
}
MOCK_100_RESPONSE = {
    "zigbee:InstantaneousDemand": "1.152000",
    "zigbee:CurrentSummationDelivered": "45251.285000",
    "zigbee:CurrentSummationReceived": "232.232000",
}


@pytest.fixture
async def setup_rainforest_200(hass):
    """Set up rainforest."""
    MockConfigEntry(
        domain="rainforest_eagle",
        data={
            CONF_CLOUD_ID: MOCK_CLOUD_ID,
            CONF_INSTALL_CODE: "abcdefgh",
            CONF_HARDWARE_ADDRESS: "mock-hw-address",
            CONF_TYPE: TYPE_EAGLE_200,
        },
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_eagle.data.EagleDataCoordinator._async_update_data_200",
        return_value=MOCK_200_RESPONSE_WITHOUT_PRICE,
    ) as mock_update:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update


@pytest.fixture
async def setup_rainforest_100(hass):
    """Set up rainforest."""
    MockConfigEntry(
        domain="rainforest_eagle",
        data={
            CONF_CLOUD_ID: MOCK_CLOUD_ID,
            CONF_INSTALL_CODE: "abcdefgh",
            CONF_HARDWARE_ADDRESS: None,
            CONF_TYPE: TYPE_EAGLE_100,
        },
    ).add_to_hass(hass)
    with patch(
        "homeassistant.components.rainforest_eagle.data.EagleDataCoordinator._fetch_data_100",
        return_value=MOCK_100_RESPONSE,
    ) as mock_update:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_update


async def test_sensors_200(hass, setup_rainforest_200):
    """Test the sensors."""
    assert len(hass.states.async_all()) == 3

    demand = hass.states.get("sensor.meter_power_demand")
    assert demand is not None
    assert demand.state == "1.152000"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.total_meter_energy_delivered")
    assert delivered is not None
    assert delivered.state == "45251.285000"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.total_meter_energy_received")
    assert received is not None
    assert received.state == "232.232000"
    assert received.attributes["unit_of_measurement"] == "kWh"

    setup_rainforest_200.return_value = MOCK_200_RESPONSE_WITH_PRICE

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 4

    price = hass.states.get("sensor.meter_price")
    assert price is not None
    assert price.state == "0.053990"
    assert price.attributes["unit_of_measurement"] == "kWh/USD"


async def test_sensors_100(hass, setup_rainforest_100):
    """Test the sensors."""
    assert len(hass.states.async_all()) == 3

    demand = hass.states.get("sensor.meter_power_demand")
    assert demand is not None
    assert demand.state == "1.152000"
    assert demand.attributes["unit_of_measurement"] == "kW"

    delivered = hass.states.get("sensor.total_meter_energy_delivered")
    assert delivered is not None
    assert delivered.state == "45251.285000"
    assert delivered.attributes["unit_of_measurement"] == "kWh"

    received = hass.states.get("sensor.total_meter_energy_received")
    assert received is not None
    assert received.state == "232.232000"
    assert received.attributes["unit_of_measurement"] == "kWh"
