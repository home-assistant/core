"""Test the Aranet sensors."""
from homeassistant.components.aranet.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import DISABLED_INTEGRATIONS_SERVICE_INFO, VALID_DATA_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_DATA_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 5

    batt_sensor = hass.states.get("sensor.aranet4_12345_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "89"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    co2_sensor = hass.states.get("sensor.aranet4_12345_carbon_dioxide")
    co2_sensor_attrs = co2_sensor.attributes
    assert co2_sensor.state == "650"
    assert co2_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Carbon Dioxide"
    assert co2_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "ppm"
    assert co2_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    humid_sensor = hass.states.get("sensor.aranet4_12345_humidity")
    humid_sensor_attrs = humid_sensor.attributes
    assert humid_sensor.state == "34"
    assert humid_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Humidity"
    assert humid_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert humid_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.aranet4_12345_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "21.1"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    press_sensor = hass.states.get("sensor.aranet4_12345_pressure")
    press_sensor_attrs = press_sensor.attributes
    assert press_sensor.state == "990.5"
    assert press_sensor_attrs[ATTR_FRIENDLY_NAME] == "Aranet4 12345 Pressure"
    assert press_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "hPa"
    assert press_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_smart_home_integration_disabled(hass: HomeAssistant) -> None:
    """Test disabling smart home integration marks entities as unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, DISABLED_INTEGRATIONS_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 5

    batt_sensor = hass.states.get("sensor.aranet4_12345_battery")
    assert batt_sensor.state == "unavailable"

    co2_sensor = hass.states.get("sensor.aranet4_12345_carbon_dioxide")
    assert co2_sensor.state == "unavailable"

    humid_sensor = hass.states.get("sensor.aranet4_12345_humidity")
    assert humid_sensor.state == "unavailable"

    temp_sensor = hass.states.get("sensor.aranet4_12345_temperature")
    assert temp_sensor.state == "unavailable"

    press_sensor = hass.states.get("sensor.aranet4_12345_pressure")
    assert press_sensor.state == "unavailable"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
