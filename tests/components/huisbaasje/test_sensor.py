"""Test cases for the sensors of the Huisbaasje integration."""
from unittest.mock import patch

from homeassistant.components import huisbaasje
from homeassistant.components.huisbaasje.const import FLOW_CUBIC_METERS_PER_HOUR
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.huisbaasje.test_data import (
    MOCK_CURRENT_MEASUREMENTS,
    MOCK_LIMITED_CURRENT_MEASUREMENTS,
)


async def test_setup_entry(hass: HomeAssistant):
    """Test for successfully loading sensor states."""
    with patch(
        "huisbaasje.Huisbaasje.authenticate", return_value=None
    ) as mock_authenticate, patch(
        "huisbaasje.Huisbaasje.is_authenticated", return_value=True
    ) as mock_is_authenticated, patch(
        "huisbaasje.Huisbaasje.current_measurements",
        return_value=MOCK_CURRENT_MEASUREMENTS,
    ) as mock_current_measurements:

        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=huisbaasje.DOMAIN,
            title="userId",
            data={
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Assert data is loaded
        current_power = hass.states.get("sensor.huisbaasje_current_power")
        assert current_power.state == "1012.0"
        assert (
            current_power.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
        )
        assert current_power.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            current_power.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert current_power.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT

        current_power_in = hass.states.get("sensor.huisbaasje_current_power_in_peak")
        assert current_power_in.state == "1012.0"
        assert (
            current_power_in.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.POWER
        )
        assert current_power_in.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            current_power_in.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert current_power_in.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT

        current_power_in_low = hass.states.get(
            "sensor.huisbaasje_current_power_in_off_peak"
        )
        assert current_power_in_low.state == "unknown"
        assert (
            current_power_in_low.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.POWER
        )
        assert current_power_in_low.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            current_power_in_low.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert (
            current_power_in_low.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
        )

        current_power_out = hass.states.get("sensor.huisbaasje_current_power_out_peak")
        assert current_power_out.state == "unknown"
        assert (
            current_power_out.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.POWER
        )
        assert current_power_out.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            current_power_out.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert current_power_out.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT

        current_power_out_low = hass.states.get(
            "sensor.huisbaasje_current_power_out_off_peak"
        )
        assert current_power_out_low.state == "unknown"
        assert (
            current_power_out_low.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.POWER
        )
        assert current_power_out_low.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            current_power_out_low.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert (
            current_power_out_low.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
        )

        energy_consumption_peak_today = hass.states.get(
            "sensor.huisbaasje_energy_consumption_peak_today"
        )
        assert energy_consumption_peak_today.state == "2.67"
        assert (
            energy_consumption_peak_today.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert (
            energy_consumption_peak_today.attributes.get(ATTR_ICON)
            == "mdi:lightning-bolt"
        )
        assert (
            energy_consumption_peak_today.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            energy_consumption_peak_today.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_consumption_off_peak_today = hass.states.get(
            "sensor.huisbaasje_energy_consumption_off_peak_today"
        )
        assert energy_consumption_off_peak_today.state == "0.627"
        assert (
            energy_consumption_off_peak_today.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert (
            energy_consumption_off_peak_today.attributes.get(ATTR_ICON)
            == "mdi:lightning-bolt"
        )
        assert (
            energy_consumption_off_peak_today.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            energy_consumption_off_peak_today.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_production_peak_today = hass.states.get(
            "sensor.huisbaasje_energy_production_peak_today"
        )
        assert energy_production_peak_today.state == "1.512"
        assert (
            energy_production_peak_today.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert (
            energy_production_peak_today.attributes.get(ATTR_ICON)
            == "mdi:lightning-bolt"
        )
        assert (
            energy_production_peak_today.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            energy_production_peak_today.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_production_off_peak_today = hass.states.get(
            "sensor.huisbaasje_energy_production_off_peak_today"
        )
        assert energy_production_off_peak_today.state == "1.093"
        assert (
            energy_production_off_peak_today.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert (
            energy_production_off_peak_today.attributes.get(ATTR_ICON)
            == "mdi:lightning-bolt"
        )
        assert (
            energy_production_off_peak_today.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            energy_production_off_peak_today.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_today = hass.states.get("sensor.huisbaasje_energy_today")
        assert energy_today.state == "3.3"
        assert (
            energy_today.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
        )
        assert energy_today.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            energy_today.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert (
            energy_today.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_this_week = hass.states.get("sensor.huisbaasje_energy_this_week")
        assert energy_this_week.state == "17.5"
        assert (
            energy_this_week.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert energy_this_week.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            energy_this_week.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert (
            energy_this_week.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_this_month = hass.states.get("sensor.huisbaasje_energy_this_month")
        assert energy_this_month.state == "103.3"
        assert (
            energy_this_month.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert energy_this_month.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            energy_this_month.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert (
            energy_this_month.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        energy_this_year = hass.states.get("sensor.huisbaasje_energy_this_year")
        assert energy_this_year.state == "673.0"
        assert (
            energy_this_year.attributes.get(ATTR_DEVICE_CLASS)
            == SensorDeviceClass.ENERGY
        )
        assert energy_this_year.attributes.get(ATTR_ICON) == "mdi:lightning-bolt"
        assert (
            energy_this_year.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.MEASUREMENT
        )
        assert (
            energy_this_year.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == ENERGY_KILO_WATT_HOUR
        )

        current_gas = hass.states.get("sensor.huisbaasje_current_gas")
        assert current_gas.state == "0.0"
        assert current_gas.attributes.get(ATTR_DEVICE_CLASS) is None
        assert current_gas.attributes.get(ATTR_ICON) == "mdi:fire"
        assert (
            current_gas.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
        )
        assert (
            current_gas.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == FLOW_CUBIC_METERS_PER_HOUR
        )

        gas_today = hass.states.get("sensor.huisbaasje_gas_today")
        assert gas_today.state == "1.1"
        assert gas_today.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
        assert gas_today.attributes.get(ATTR_ICON) == "mdi:counter"
        assert (
            gas_today.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert gas_today.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_CUBIC_METERS

        gas_this_week = hass.states.get("sensor.huisbaasje_gas_this_week")
        assert gas_this_week.state == "5.6"
        assert gas_this_week.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
        assert gas_this_week.attributes.get(ATTR_ICON) == "mdi:counter"
        assert (
            gas_this_week.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            gas_this_week.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == VOLUME_CUBIC_METERS
        )

        gas_this_month = hass.states.get("sensor.huisbaasje_gas_this_month")
        assert gas_this_month.state == "39.1"
        assert gas_this_month.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
        assert gas_this_month.attributes.get(ATTR_ICON) == "mdi:counter"
        assert (
            gas_this_month.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            gas_this_month.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == VOLUME_CUBIC_METERS
        )

        gas_this_year = hass.states.get("sensor.huisbaasje_gas_this_year")
        assert gas_this_year.state == "116.7"
        assert gas_this_year.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
        assert gas_this_year.attributes.get(ATTR_ICON) == "mdi:counter"
        assert (
            gas_this_year.attributes.get(ATTR_STATE_CLASS)
            is SensorStateClass.TOTAL_INCREASING
        )
        assert (
            gas_this_year.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            == VOLUME_CUBIC_METERS
        )

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1
        assert len(mock_is_authenticated.mock_calls) == 1
        assert len(mock_current_measurements.mock_calls) == 1


async def test_setup_entry_absent_measurement(hass: HomeAssistant):
    """Test for successfully loading sensor states when response does not contain all measurements."""
    with patch(
        "huisbaasje.Huisbaasje.authenticate", return_value=None
    ) as mock_authenticate, patch(
        "huisbaasje.Huisbaasje.is_authenticated", return_value=True
    ) as mock_is_authenticated, patch(
        "huisbaasje.Huisbaasje.current_measurements",
        return_value=MOCK_LIMITED_CURRENT_MEASUREMENTS,
    ) as mock_current_measurements:

        hass.config.components.add(huisbaasje.DOMAIN)
        config_entry = MockConfigEntry(
            version=1,
            domain=huisbaasje.DOMAIN,
            title="userId",
            data={
                CONF_ID: "userId",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
            source="test",
        )
        config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Assert data is loaded
        assert hass.states.get("sensor.huisbaasje_current_power").state == "1012.0"
        assert (
            hass.states.get("sensor.huisbaasje_current_power_in_peak").state
            == "unknown"
        )
        assert (
            hass.states.get("sensor.huisbaasje_current_power_in_off_peak").state
            == "unknown"
        )
        assert (
            hass.states.get("sensor.huisbaasje_current_power_out_peak").state
            == "unknown"
        )
        assert (
            hass.states.get("sensor.huisbaasje_current_power_out_off_peak").state
            == "unknown"
        )
        assert hass.states.get("sensor.huisbaasje_current_gas").state == "unknown"
        assert hass.states.get("sensor.huisbaasje_energy_today").state == "3.3"
        assert (
            hass.states.get("sensor.huisbaasje_energy_consumption_peak_today").state
            == "unknown"
        )
        assert (
            hass.states.get("sensor.huisbaasje_energy_consumption_off_peak_today").state
            == "unknown"
        )
        assert (
            hass.states.get("sensor.huisbaasje_energy_production_peak_today").state
            == "unknown"
        )
        assert (
            hass.states.get("sensor.huisbaasje_energy_production_off_peak_today").state
            == "unknown"
        )
        assert hass.states.get("sensor.huisbaasje_gas_today").state == "unknown"

        # Assert mocks are called
        assert len(mock_authenticate.mock_calls) == 1
        assert len(mock_is_authenticated.mock_calls) == 1
        assert len(mock_current_measurements.mock_calls) == 1
