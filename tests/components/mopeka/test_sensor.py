"""Test the Mopeka sensors."""

import pytest

from homeassistant.components.mopeka.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from . import (
    PRO_GOOD_SIGNAL_SERVICE_INFO,
    PRO_SERVICE_INFO,
    PRO_UNUSABLE_SIGNAL_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors_unusable_signal(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors when there is unusable signal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, PRO_UNUSABLE_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    temp_sensor = hass.states.get("sensor.pro_plus_eeff_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "30"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    tank_sensor = hass.states.get("sensor.pro_plus_eeff_tank_level")
    tank_sensor_attrs = tank_sensor.attributes
    assert tank_sensor.state == STATE_UNKNOWN
    assert tank_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Tank Level"
    assert tank_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert tank_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_poor_signal(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors when there is poor signal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, PRO_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    temp_sensor = hass.states.get("sensor.pro_plus_eeff_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "30"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    tank_sensor = hass.states.get("sensor.pro_plus_eeff_tank_level")
    tank_sensor_attrs = tank_sensor.attributes
    assert tank_sensor.state == "0"
    assert tank_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Tank Level"
    assert tank_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert tank_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_good_signal(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors when there is good signal."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, PRO_GOOD_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 4

    temp_sensor = hass.states.get("sensor.pro_plus_eeff_temperature")
    temp_sensor_attrs = temp_sensor.attributes
    assert temp_sensor.state == "27"
    assert temp_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Temperature"
    assert temp_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert temp_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    tank_sensor = hass.states.get("sensor.pro_plus_eeff_tank_level")
    tank_sensor_attrs = tank_sensor.attributes
    assert tank_sensor.state == "341"
    assert tank_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Tank Level"
    assert tank_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert tank_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_tank_level_raw_sensor(hass: HomeAssistant) -> None:
    """Test the raw tank level sensor follows the reading quality gating."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, PRO_UNUSABLE_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()

    raw_sensor = hass.states.get("sensor.pro_plus_eeff_tank_level_raw")
    raw_sensor_attrs = raw_sensor.attributes
    assert raw_sensor.state == STATE_UNKNOWN
    assert raw_sensor_attrs[ATTR_FRIENDLY_NAME] == "Pro Plus EEFF Tank level raw"
    assert raw_sensor_attrs[ATTR_STATE_CLASS] == "measurement"
    assert ATTR_UNIT_OF_MEASUREMENT not in raw_sensor_attrs

    inject_bluetooth_service_info(hass, PRO_GOOD_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pro_plus_eeff_tank_level_raw").state == "950"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
