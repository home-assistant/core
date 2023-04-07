"""Tests for Broadlink sensors."""
from datetime import timedelta

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.updater import BroadlinkSP4UpdateManager
from homeassistant.const import ATTR_FRIENDLY_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt

from . import get_device

from tests.common import async_fire_time_changed


async def test_a1_sensor_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
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

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_api.check_sensors_raw.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 5

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "27.4"),
        (f"{device.name} Humidity", "59.3"),
        (f"{device.name} Air quality index", "3"),
        (f"{device.name} Illuminance", "2"),
        (f"{device.name} Noise", "1"),
    }


async def test_a1_sensor_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
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

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 5

    mock_setup.api.check_sensors_raw.return_value = {
        "temperature": 22.5,
        "humidity": 47.4,
        "air_quality": 2,
        "light": 3,
        "noise": 2,
    }
    await async_update_entity(hass, next(iter(sensors)).entity_id)
    assert mock_setup.api.check_sensors_raw.call_count == 2

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "22.5"),
        (f"{device.name} Humidity", "47.4"),
        (f"{device.name} Air quality index", "2"),
        (f"{device.name} Illuminance", "3"),
        (f"{device.name} Noise", "2"),
    }


async def test_rm_pro_sensor_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful RM pro sensor setup."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 18.2}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_api.check_sensors.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 1

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {(f"{device.name} Temperature", "18.2")}


async def test_rm_pro_sensor_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful RM pro sensor update."""
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 25.7}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 1

    mock_setup.api.check_sensors.return_value = {"temperature": 25.8}
    await async_update_entity(hass, next(iter(sensors)).entity_id)
    assert mock_setup.api.check_sensors.call_count == 2

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {(f"{device.name} Temperature", "25.8")}


async def test_rm_pro_filter_crazy_temperature(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we filter a crazy temperature variation.

    Firmware issue. See https://github.com/home-assistant/core/issues/42100.
    """
    device = get_device("Office")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 22.9}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 1

    mock_setup.api.check_sensors.return_value = {"temperature": -7}
    await async_update_entity(hass, next(iter(sensors)).entity_id)
    assert mock_setup.api.check_sensors.call_count == 2

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {(f"{device.name} Temperature", "22.9")}


async def test_rm_mini3_no_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we do not set up sensors for RM mini 3."""
    device = get_device("Entrance")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 0}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_api.check_sensors.call_count <= 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 0


async def test_rm4_pro_hts2_sensor_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful RM4 pro sensor setup with HTS2 cable."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 22.5, "humidity": 43.7}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_api.check_sensors.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 2

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "22.5"),
        (f"{device.name} Humidity", "43.7"),
    }


async def test_rm4_pro_hts2_sensor_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful RM4 pro sensor update with HTS2 cable."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 16.7, "humidity": 34.1}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 2

    mock_setup.api.check_sensors.return_value = {"temperature": 16.8, "humidity": 34.0}
    await async_update_entity(hass, next(iter(sensors)).entity_id)
    assert mock_setup.api.check_sensors.call_count == 2

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Temperature", "16.8"),
        (f"{device.name} Humidity", "34.0"),
    }


async def test_rm4_pro_no_sensor(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we do not set up sensors for RM4 pro without HTS2 cable."""
    device = get_device("Garage")
    mock_api = device.get_mock_api()
    mock_api.check_sensors.return_value = {"temperature": 0, "humidity": 0}

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_api.check_sensors.call_count <= 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = {entry for entry in entries if entry.domain == Platform.SENSOR}
    assert len(sensors) == 0


async def test_scb1e_sensor_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful SCB1E sensor setup."""
    device = get_device("Dining room")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "pwr": 1,
        "indicator": 1,
        "maxworktime": 0,
        "power": 255.57,
        "volt": 121.7,
        "current": 2.1,
        "overload": 0,
        "totalconsum": 1.7,
        "childlock": 0,
    }

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert mock_api.get_state.call_count == 1
    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 5

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Power", "255.57"),
        (f"{device.name} Voltage", "121.7"),
        (f"{device.name} Current", "2.1"),
        (f"{device.name} Overload", "0"),
        (f"{device.name} Total consumption", "1.7"),
    }


async def test_scb1e_sensor_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a successful SCB1E sensor update."""
    device = get_device("Dining room")
    mock_api = device.get_mock_api()
    mock_api.get_state.return_value = {
        "pwr": 1,
        "indicator": 1,
        "maxworktime": 0,
        "power": 255.6,
        "volt": 121.7,
        "current": 2.1,
        "overload": 0,
        "totalconsum": 1.7,
        "childlock": 0,
    }

    target_time = (
        dt.utcnow() + BroadlinkSP4UpdateManager.SCAN_INTERVAL * 3 + timedelta(seconds=1)
    )

    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    device_entry = device_registry.async_get_device(
        {(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    sensors = [entry for entry in entries if entry.domain == Platform.SENSOR]
    assert len(sensors) == 5

    mock_setup.api.get_state.return_value = {
        "pwr": 1,
        "indicator": 1,
        "maxworktime": 0,
        "power": 291.8,
        "volt": 121.6,
        "current": 2.4,
        "overload": 0,
        "totalconsum": 0.5,
        "childlock": 0,
    }

    async_fire_time_changed(hass, target_time)
    await hass.async_block_till_done()

    assert mock_setup.api.get_state.call_count == 2

    sensors_and_states = {
        (
            hass.states.get(sensor.entity_id).attributes[ATTR_FRIENDLY_NAME],
            hass.states.get(sensor.entity_id).state,
        )
        for sensor in sensors
    }
    assert sensors_and_states == {
        (f"{device.name} Power", "291.8"),
        (f"{device.name} Voltage", "121.6"),
        (f"{device.name} Current", "2.4"),
        (f"{device.name} Overload", "0"),
        (f"{device.name} Total consumption", "0.5"),
    }
