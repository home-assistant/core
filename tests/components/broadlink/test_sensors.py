"""Tests for Broadlink sensors."""
from homeassistant.components.broadlink.const import DOMAIN, SENSOR_DOMAIN
from homeassistant.helpers.entity_registry import async_entries_for_device

from . import get_device

from tests.async_mock import patch
from tests.common import mock_device_registry, mock_registry


def _patch_broadlink_gendevice(return_value):
    """Patch the broadlink gendevice method."""
    return patch(
        "homeassistant.components.broadlink.device.blk.gendevice",
        return_value=return_value,
    )


async def test_a1_sensor_setup(hass):
    """Test a successful e-Sensor setup."""
    device = get_device("Bedroom")
    mock_api = device.get_mock_api()
    mock_api.check_sensors_raw.return_value = {
        "temperature": 27.4,
        "humidity": 59.3,
        "air_quality": 3,
        "light": 2,
        "noise": 1,
    }
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_api.check_sensors_raw.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 5

    sensors_and_states = {
        (sensor.original_name, hass.states.get(sensor.entity_id).state)
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "27.4"),
        (f"{device.name} Humidity", "59.3"),
        (f"{device.name} Air Quality", "3"),
        (f"{device.name} Light", "2"),
        (f"{device.name} Noise", "1"),
    }


async def test_a1_sensor_update(hass):
    """Test a successful e-Sensor update."""
    device = get_device("Bedroom")
    mock_api = device.get_mock_api()
    mock_api.check_sensors_raw.return_value = {
        "temperature": 22.4,
        "humidity": 47.3,
        "air_quality": 3,
        "light": 2,
        "noise": 1,
    }
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 5

    mock_api.check_sensors_raw.return_value = {
        "temperature": 22.5,
        "humidity": 47.4,
        "air_quality": 2,
        "light": 3,
        "noise": 2,
    }
    await hass.helpers.entity_component.async_update_entity(
        next(iter(sensors)).entity_id
    )
    assert mock_api.check_sensors_raw.call_count == 2

    sensors_and_states = {
        (sensor.original_name, hass.states.get(sensor.entity_id).state)
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "22.5"),
        (f"{device.name} Humidity", "47.4"),
        (f"{device.name} Air Quality", "2"),
        (f"{device.name} Light", "3"),
        (f"{device.name} Noise", "2"),
    }


async def test_rm_pro_sensor_setup(hass):
    """Test a successful RM pro sensor setup."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 18.2}
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_api.check_sensors.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 1

    sensors_and_states = {
        (sensor.original_name, hass.states.get(sensor.entity_id).state)
        for sensor in sensors
    }
    assert sensors_and_states == {(f"{device.name} Temperature", "18.2")}


async def test_rm_pro_sensor_update(hass):
    """Test a successful RM pro sensor update."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 25.7}
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 1

    mock_api.check_sensors.return_value = {"temperature": 25.8}
    await hass.helpers.entity_component.async_update_entity(
        next(iter(sensors)).entity_id
    )
    assert mock_api.check_sensors.call_count == 2

    sensors_and_states = {
        (sensor.original_name, hass.states.get(sensor.entity_id).state)
        for sensor in sensors
    }
    assert sensors_and_states == {(f"{device.name} Temperature", "25.8")}


async def test_rm_mini3_no_sensor(hass):
    """Test we do not set up sensors for RM mini 3."""
    device = get_device("Entrance")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 0}
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_api.check_sensors.call_count <= 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 0


async def test_rm4_pro_hts2_sensor_setup(hass):
    """Test a successful RM4 pro sensor setup with HTS2 cable."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 22.5, "humidity": 43.7}
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_api.check_sensors.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 2

    sensors_and_states = {
        (sensor.original_name, hass.states.get(sensor.entity_id).state)
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "22.5"),
        (f"{device.name} Humidity", "43.7"),
    }


async def test_rm4_pro_hts2_sensor_update(hass):
    """Test a successful RM4 pro sensor update with HTS2 cable."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 16.7, "humidity": 34.1}
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 2

    mock_api.check_sensors.return_value = {"temperature": 16.8, "humidity": 34.0}
    await hass.helpers.entity_component.async_update_entity(
        next(iter(sensors)).entity_id
    )
    assert mock_api.check_sensors.call_count == 2

    sensors_and_states = {
        (sensor.original_name, hass.states.get(sensor.entity_id).state)
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "16.8"),
        (f"{device.name} Humidity", "34.0"),
    }


async def test_rm4_pro_no_sensor(hass):
    """Test we do not set up sensors for RM4 pro without HTS2 cable."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 0, "humidity": 0}
    mock_entry = device.get_mock_entry()
    mock_entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    entity_registry = mock_registry(hass)

    with _patch_broadlink_gendevice(return_value=mock_api):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_api.check_sensors.call_count <= 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_entry.unique_id)}, set()
    )
    entries = async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == SENSOR_DOMAIN}
    assert len(sensors) == 0
