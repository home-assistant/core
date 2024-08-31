"""Test the Leaone sensors."""

from homeassistant.components.leaone.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from . import SCALE_SERVICE_INFO, SCALE_SERVICE_INFO_2, SCALE_SERVICE_INFO_3

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="5F:5A:5C:52:D3:94",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0

    inject_bluetooth_service_info(hass, SCALE_SERVICE_INFO)
    await hass.async_block_till_done()
    inject_bluetooth_service_info(hass, SCALE_SERVICE_INFO_2)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 2

    mass_sensor = hass.states.get("sensor.tzc4_d394_mass")
    mass_sensor_attrs = mass_sensor.attributes
    assert mass_sensor.state == "77.11"
    assert mass_sensor_attrs[ATTR_FRIENDLY_NAME] == "TZC4 D394 Mass"
    assert mass_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "kg"
    assert mass_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    mass_sensor = hass.states.get("sensor.tzc4_d394_non_stabilized_mass")
    mass_sensor_attrs = mass_sensor.attributes
    assert mass_sensor.state == "77.11"
    assert mass_sensor_attrs[ATTR_FRIENDLY_NAME] == "TZC4 D394 Non Stabilized Mass"
    assert mass_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "kg"
    assert mass_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    inject_bluetooth_service_info(hass, SCALE_SERVICE_INFO_3)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
