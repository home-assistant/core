"""Test the MikroTik BT5 sensors."""

from homeassistant.components.mikrotik_bt5.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import UNSUPPORTED_VERSION_DATA, VALID_DATA, VALID_NO_TEMPERATURE_DATA

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors_bt5_v1(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test setting up creates the sensors for v1 beacon with temperature data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_DATA)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    batt_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "82"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    temp_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "22.5"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "°C"
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    accel_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_acceleration")
    accel_sensor_attrs = accel_sensor.attributes
    assert 0.358520 <= float(accel_sensor.state) <= 0.358530
    assert (
        accel_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Acceleration"
    )
    assert accel_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "m/s²"
    assert accel_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    uptime_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_uptime")
    uptime_sensor_attrs = uptime_sensor.attributes
    assert uptime_sensor.state == "81403619"
    assert uptime_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Uptime"
    assert uptime_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "s"
    assert uptime_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_bt5_v1_no_temperature(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test setting up creates the sensors for Aranet4 device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, VALID_NO_TEMPERATURE_DATA)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 3

    assert hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_temperature") is None

    batt_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_battery")
    batt_sensor_attrs = batt_sensor.attributes
    assert batt_sensor.state == "100"
    assert batt_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Battery"
    assert batt_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "%"
    assert batt_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    accel_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_acceleration")
    accel_sensor_attrs = accel_sensor.attributes
    assert 1.328760 <= float(accel_sensor.state) <= 1.328770
    assert (
        accel_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Acceleration"
    )
    assert accel_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "m/s²"
    assert accel_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    uptime_sensor = hass.states.get("sensor.bt5_aa_bb_cc_dd_ee_ff_uptime")
    uptime_sensor_attrs = uptime_sensor.attributes
    assert uptime_sensor.state == "81403619"
    assert uptime_sensor_attrs[ATTR_FRIENDLY_NAME] == "BT5 AA:BB:CC:DD:EE:FF Uptime"
    assert uptime_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "s"
    assert uptime_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensor_unsupported_version(
    hass: HomeAssistant, entity_registry_enabled_by_default: None
) -> None:
    """Test disabling smart home integration marks entities as unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, UNSUPPORTED_VERSION_DATA)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 0

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
