"""Test cases for the sensors of the Huisbaasje integration."""
from homeassistant.components import huisbaasje
from homeassistant.config_entries import CONN_CLASS_CLOUD_POLL, ConfigEntry
from homeassistant.core import HomeAssistant

from tests.async_mock import patch

MOCK_CURRENT_MEASUREMENTS = {
    "electricity": {
        "measurement": {
            "time": "2020-11-18T15:17:24.000Z",
            "rate": 1011.6666666666667,
            "value": 0.0033333333333333335,
            "costPerHour": 0.20233333333333337,
            "counterValue": 409.17166666631937,
        },
        "thisDay": {"value": 3.296665869, "cost": 0.6593331738},
        "thisWeek": {"value": 17.509996085, "cost": 3.5019992170000003},
        "thisMonth": {"value": 103.28830788, "cost": 20.657661576000002},
        "thisYear": {"value": 672.9781177300001, "cost": 134.595623546},
    },
    "electricityIn": {
        "measurement": {
            "time": "2020-11-18T15:17:24.000Z",
            "rate": 1011.6666666666667,
            "value": 0.0033333333333333335,
            "costPerHour": 0.20233333333333337,
            "counterValue": 409.17166666631937,
        },
        "thisDay": {"value": 2.669999453, "cost": 0.5339998906},
        "thisWeek": {"value": 15.328330291, "cost": 3.0656660582},
        "thisMonth": {"value": 72.986651896, "cost": 14.5973303792},
        "thisYear": {"value": 409.214880212, "cost": 81.84297604240001},
    },
    "electricityInLow": {
        "measurement": None,
        "thisDay": {"value": 0.6266664160000001, "cost": 0.1253332832},
        "thisWeek": {"value": 2.181665794, "cost": 0.43633315880000006},
        "thisMonth": {"value": 30.301655984000003, "cost": 6.060331196800001},
        "thisYear": {"value": 263.76323751800004, "cost": 52.75264750360001},
    },
    "electricityOut": {
        "measurement": None,
        "thisDay": {"value": 0.0, "cost": 0.0},
        "thisWeek": {"value": 0.0, "cost": 0.0},
        "thisMonth": {"value": 0.0, "cost": 0.0},
        "thisYear": {"value": 0.0, "cost": 0.0},
    },
    "electricityOutLow": {
        "measurement": None,
        "thisDay": {"value": 0.0, "cost": 0.0},
        "thisWeek": {"value": 0.0, "cost": 0.0},
        "thisMonth": {"value": 0.0, "cost": 0.0},
        "thisYear": {"value": 0.0, "cost": 0.0},
    },
    "gas": {
        "measurement": {
            "time": "2020-11-18T15:17:29.000Z",
            "rate": 0.0,
            "value": 0.0,
            "costPerHour": 0.0,
            "counterValue": 116.73000000002281,
        },
        "thisDay": {"value": 1.07, "cost": 0.642},
        "thisWeek": {"value": 5.634224386000001, "cost": 3.3805346316000007},
        "thisMonth": {"value": 39.14, "cost": 23.483999999999998},
        "thisYear": {"value": 116.73, "cost": 70.038},
    },
}

MOCK_LIMITED_CURRENT_MEASUREMENTS = {
    "electricity": {
        "measurement": {
            "time": "2020-11-18T15:17:24.000Z",
            "rate": 1011.6666666666667,
            "value": 0.0033333333333333335,
            "costPerHour": 0.20233333333333337,
            "counterValue": 409.17166666631937,
        },
        "thisDay": {"value": 3.296665869, "cost": 0.6593331738},
        "thisWeek": {"value": 17.509996085, "cost": 3.5019992170000003},
        "thisMonth": {"value": 103.28830788, "cost": 20.657661576000002},
        "thisYear": {"value": 672.9781177300001, "cost": 134.595623546},
    }
}


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
                huisbaasje.CONF_ID: "userId",
                huisbaasje.CONF_USERNAME: "username",
                huisbaasje.CONF_PASSWORD: "password",
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
        assert hass.states.get("sensor.huisbaasje_gas_today").state == "1.1"


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
                huisbaasje.CONF_ID: "userId",
                huisbaasje.CONF_USERNAME: "username",
                huisbaasje.CONF_PASSWORD: "password",
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
