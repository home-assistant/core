"""Tests for the srp_energy sensor platform."""
from unittest.mock import patch

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.components.srp_energy.const import CONF_IS_TOU, DOMAIN, SENSORS_INFO
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CURRENCY_DOLLAR,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    ENERGY_KILO_WATT_HOUR,
)

from tests.common import MockConfigEntry

sample_usage = [
    ("9/19/2018", "12:00 AM", "2018-09-19T00:00:00-7:00", "1.2", "0.17"),
    ("9/19/2018", "1:00 AM", "2018-09-19T01:00:00-7:00", "2.1", "0.30"),
    ("9/19/2018", "2:00 AM", "2018-09-19T02:00:00-7:00", "1.5", "0.23"),
    ("9/19/2018", "9:00 PM", "2018-09-19T21:00:00-7:00", "1.2", "0.19"),
    ("9/19/2018", "10:00 PM", "2018-09-19T22:00:00-7:00", "1.1", "0.18"),
    ("9/19/2018", "11:00 PM", "2018-09-19T23:00:00-7:00", "0.4", "0.09"),
]


async def test_setup_entry(hass):
    """Test for successfully setting up the platform."""
    with patch(
        "srpenergy.client.SrpEnergyClient.usage", return_value=sample_usage
    ), patch(
        "homeassistant.components.srp_energy.SrpEnergyClient.usage",
        return_value=sample_usage,
    ):

        hass.config.components.add(DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_NAME: "Test",
                CONF_ID: "123456789",
                CONF_USERNAME: "abba",
                CONF_PASSWORD: "ana",
                CONF_IS_TOU: False,
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert DOMAIN in hass.config.components

        # Assert data is loaded for usage
        current_usage = hass.states.get("sensor.srp_energy_usage")
        assert current_usage.state == "7.5"
        assert current_usage.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
        assert (
            current_usage.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )
        assert (
            current_usage.attributes.get(ATTR_STATE_CLASS)
            == STATE_CLASS_TOTAL_INCREASING
        )
        assert current_usage.attributes.get(ATTR_FRIENDLY_NAME) == "SRP Energy Usage"
        assert current_usage.attributes.get(ATTR_ICON) == "mdi:flash"

        # Assert data is loaded for cost
        current_costs = hass.states.get("sensor.srp_energy_costs")
        assert current_costs.state == "1.16"
        assert current_costs.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_MONETARY
        assert current_costs.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == CURRENCY_DOLLAR
        assert (
            current_costs.attributes.get(ATTR_STATE_CLASS)
            == STATE_CLASS_TOTAL_INCREASING
        )
        assert current_costs.attributes.get(ATTR_FRIENDLY_NAME) == "SRP Energy Costs"
        assert current_costs.attributes.get(ATTR_ICON) == "mdi:cash"


async def test_async_setup_entry_timeout_error(hass):
    """Test fetching usage data. Failed the first time because was too get response."""
    with patch(
        "srpenergy.client.SrpEnergyClient.usage", side_effect=TimeoutError()
    ), patch(
        "homeassistant.components.srp_energy.SrpEnergyClient.usage",
        side_effect=TimeoutError(),
    ):
        hass.config.components.add(DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_NAME: "Test",
                CONF_ID: "123456789",
                CONF_USERNAME: "abba",
                CONF_PASSWORD: "ana",
                CONF_IS_TOU: False,
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert DOMAIN in hass.config.components


async def test_async_setup_entry_connect_error(hass):
    """Test fetching usage data. Failed the first time because was too get response."""
    with patch(
        "srpenergy.client.SrpEnergyClient.usage", side_effect=ValueError()
    ), patch(
        "homeassistant.components.srp_energy.SrpEnergyClient.usage",
        side_effect=ValueError(),
    ):
        hass.config.components.add(DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_NAME: "SRP Energy Test",
                CONF_ID: "123456789",
                CONF_USERNAME: "abba",
                CONF_PASSWORD: "ana",
                CONF_IS_TOU: False,
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert DOMAIN in hass.config.components


async def test_srp_entity_missing_type(hass):
    """Test the SrpEntity when type is missing."""
    with patch("srpenergy.client.SrpEnergyClient.usage"):
        SENSORS_INFO.append(
            {
                "name": "Test Costs",
                "device_class": DEVICE_CLASS_MONETARY,
                "unit_of_measurement": CURRENCY_DOLLAR,
                "source_type": "Abba",
                "sensor_type": "Dabba",
                "state_class": STATE_CLASS_TOTAL_INCREASING,
                "icon": "mdi:cash",
                "precision": 3,
            }
        )
        hass.config.components.add(DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=DOMAIN,
            title="userId",
            data={
                CONF_NAME: "Test",
                CONF_ID: "123456789",
                CONF_USERNAME: "abba",
                CONF_PASSWORD: "ana",
                CONF_IS_TOU: False,
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert DOMAIN in hass.config.components

        current_costs = hass.states.get("sensor.test_costs")
        assert current_costs.state == "unavailable"
