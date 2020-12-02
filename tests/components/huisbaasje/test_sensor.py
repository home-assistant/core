"""Test cases for the sensors of the Huisbaasje integration."""
from homeassistant.components import huisbaasje
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigEntry
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.async_mock import patch
from tests.components.huisbaasje.test_data import (
    MOCK_CURRENT_MEASUREMENTS,
    MOCK_LIMITED_CURRENT_MEASUREMENTS,
)


async def test_setup_entry(hass: HomeAssistant):
    """Test for successfully loading sensor states."""
    with patch(
        "huisbaasje.Huisbaasje.current_measurements",
        return_value=MOCK_CURRENT_MEASUREMENTS,
    ):

        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = ConfigEntry(
            1,
            huisbaasje.DOMAIN,
            "userId",
            {
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            "test",
            CONN_CLASS_CLOUD_POLL,
            system_options={},
        )
        hass.config_entries._entries.append(config_entry)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Assert data is loaded
        assert hass.states.get("sensor.huisbaasje_current_power").state == "1012.0"
        assert hass.states.get("sensor.huisbaasje_current_power_in").state == "1012.0"
        assert (
            hass.states.get("sensor.huisbaasje_current_power_in_low").state == "unknown"
        )
        assert hass.states.get("sensor.huisbaasje_current_power_out").state == "unknown"
        assert (
            hass.states.get("sensor.huisbaasje_current_power_out_low").state
            == "unknown"
        )
        assert hass.states.get("sensor.huisbaasje_current_gas").state == "0.0"
        assert hass.states.get("sensor.huisbaasje_energy_today").state == "3.3"
        assert hass.states.get("sensor.huisbaasje_energy_this_week").state == "17.5"
        assert hass.states.get("sensor.huisbaasje_energy_this_month").state == "103.3"
        assert hass.states.get("sensor.huisbaasje_energy_this_year").state == "673.0"
        assert hass.states.get("sensor.huisbaasje_gas_today").state == "1.1"
        assert hass.states.get("sensor.huisbaasje_gas_this_week").state == "5.6"
        assert hass.states.get("sensor.huisbaasje_gas_this_month").state == "39.1"
        assert hass.states.get("sensor.huisbaasje_gas_this_year").state == "116.7"


async def test_setup_entry_absent_measurement(hass: HomeAssistant):
    """Test for successfully loading sensor states when response does not contain all measurements."""
    with patch(
        "huisbaasje.Huisbaasje.current_measurements",
        return_value=MOCK_LIMITED_CURRENT_MEASUREMENTS,
    ):

        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = ConfigEntry(
            1,
            huisbaasje.DOMAIN,
            "userId",
            {
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            "test",
            CONN_CLASS_CLOUD_POLL,
            system_options={},
        )
        hass.config_entries._entries.append(config_entry)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Assert data is loaded
        assert hass.states.get("sensor.huisbaasje_current_power").state == "1012.0"
        assert hass.states.get("sensor.huisbaasje_current_power_in").state == "unknown"
        assert (
            hass.states.get("sensor.huisbaasje_current_power_in_low").state == "unknown"
        )
        assert hass.states.get("sensor.huisbaasje_current_power_out").state == "unknown"
        assert (
            hass.states.get("sensor.huisbaasje_current_power_out_low").state
            == "unknown"
        )
        assert hass.states.get("sensor.huisbaasje_current_gas").state == "unknown"
        assert hass.states.get("sensor.huisbaasje_energy_today").state == "3.3"
        assert hass.states.get("sensor.huisbaasje_gas_today").state == "unknown"
