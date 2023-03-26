"""Philips Hue sensor platform tests for V2 bridge/api."""
from homeassistant.components import hue
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import setup_bridge, setup_platform
from .const import FAKE_DEVICE, FAKE_SENSOR, FAKE_ZIGBEE_CONNECTIVITY


async def test_sensors(
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data
) -> None:
    """Test if all v2 sensors get created with correct features."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)

    await setup_platform(hass, mock_bridge_v2, "sensor")
    # there shouldn't have been any requests at this point
    assert len(mock_bridge_v2.mock_requests) == 0
    # 6 entities should be created from test data
    assert len(hass.states.async_all()) == 6

    # test temperature sensor
    sensor = hass.states.get("sensor.hue_motion_sensor_temperature")
    assert sensor is not None
    assert sensor.state == "18.1"
    assert sensor.attributes["friendly_name"] == "Hue motion sensor Temperature"
    assert sensor.attributes["device_class"] == "temperature"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "°C"
    assert sensor.attributes["temperature_valid"] is True

    # test illuminance sensor
    sensor = hass.states.get("sensor.hue_motion_sensor_illuminance")
    assert sensor is not None
    assert sensor.state == "63"
    assert sensor.attributes["friendly_name"] == "Hue motion sensor Illuminance"
    assert sensor.attributes["device_class"] == "illuminance"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "lx"
    assert sensor.attributes["light_level"] == 18027
    assert sensor.attributes["light_level_valid"] is True

    # test battery sensor
    sensor = hass.states.get("sensor.wall_switch_with_2_controls_battery")
    assert sensor is not None
    assert sensor.state == "100"
    assert sensor.attributes["friendly_name"] == "Wall switch with 2 controls Battery"
    assert sensor.attributes["device_class"] == "battery"
    assert sensor.attributes["state_class"] == "measurement"
    assert sensor.attributes["unit_of_measurement"] == "%"
    assert sensor.attributes["battery_state"] == "normal"

    # test disabled zigbee_connectivity sensor
    entity_id = "sensor.wall_switch_with_2_controls_zigbee_connectivity"
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_enable_sensor(
    hass: HomeAssistant, mock_bridge_v2, v2_resources_test_data, mock_config_entry_v2
) -> None:
    """Test enabling of the by default disabled zigbee_connectivity sensor."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    await setup_bridge(hass, mock_bridge_v2, mock_config_entry_v2)

    assert await async_setup_component(hass, hue.DOMAIN, {}) is True
    await hass.async_block_till_done()
    await hass.config_entries.async_forward_entry_setup(mock_config_entry_v2, "sensor")

    entity_id = "sensor.wall_switch_with_2_controls_zigbee_connectivity"
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # enable the entity
    updated_entry = ent_reg.async_update_entity(
        entity_entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload platform and check if entity is correctly there
    await hass.config_entries.async_forward_entry_unload(mock_config_entry_v2, "sensor")
    await hass.config_entries.async_forward_entry_setup(mock_config_entry_v2, "sensor")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "connected"
    assert state.attributes["mac_address"] == "00:17:88:01:0b:aa:bb:99"


async def test_sensor_add_update(hass: HomeAssistant, mock_bridge_v2) -> None:
    """Test if sensors get added/updated from events."""
    await mock_bridge_v2.api.load_test_data([FAKE_DEVICE, FAKE_ZIGBEE_CONNECTIVITY])
    await setup_platform(hass, mock_bridge_v2, "sensor")

    test_entity_id = "sensor.hue_mocked_device_temperature"

    # verify entity does not exist before we start
    assert hass.states.get(test_entity_id) is None

    # Add new fake sensor by emitting event
    mock_bridge_v2.api.emit_event("add", FAKE_SENSOR)
    await hass.async_block_till_done()

    # the entity should now be available
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "18.0"

    # test update of entity works on incoming event
    updated_sensor = {**FAKE_SENSOR, "temperature": {"temperature": 22.5}}
    mock_bridge_v2.api.emit_event("update", updated_sensor)
    await hass.async_block_till_done()
    test_entity = hass.states.get(test_entity_id)
    assert test_entity is not None
    assert test_entity.state == "22.5"
