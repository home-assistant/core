"""Test HAVEN IAQ sensors."""

from unittest.mock import AsyncMock, patch

from haveniaq import DeviceInfo, SensorData
import pytest

from homeassistant.components.haven.const import DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import TEST_CAM_INFO, TEST_CAM_SENSORS, TEST_HOST, TEST_INFO, TEST_SENSORS

from tests.common import MockConfigEntry


async def _setup_entry(
    hass: HomeAssistant,
    info: dict = TEST_INFO,
    sensors: dict | None = TEST_SENSORS,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.haven.HavenClient") as client_class:
        client = AsyncMock()
        client.get_info.return_value = DeviceInfo.from_dict(info)
        if sensors is not None:
            client.get_sensors.return_value = SensorData.from_dict(sensors)
        client_class.return_value = client
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_ram_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test RAM entities and device metadata."""
    await _setup_entry(hass)

    assert len(hass.states.async_all("sensor")) == 15
    temp_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-RAM-0001_temperature_c"
    )
    assert temp_entity is not None
    temp_state = hass.states.get(temp_entity)
    assert temp_state is not None
    assert temp_state.state == "22.5"
    assert temp_state.attributes[ATTR_FRIENDLY_NAME] == (
        "Room Air Monitor TEST-RAM-0001 Temperature"
    )
    assert temp_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "°C"

    entity = entity_registry.async_get(temp_entity)
    assert entity is not None
    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert device.manufacturer == "HAVEN IAQ"
    assert device.model == "Room Air Monitor"
    assert device.sw_version == "test-firmware"
    assert device.hw_version == "test-hardware"
    assert device.serial_number == "TEST-RAM-0001"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cam_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test CAM-specific entities replace RAM-only entities."""
    await _setup_entry(hass, TEST_CAM_INFO, TEST_CAM_SENSORS)

    assert len(hass.states.async_all("sensor")) == 11
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-CAM-0001_airflow_mps"
    )
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-CAM-0001_pressure_kpa"
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, "TEST-CAM-0001_nox_index")
        is None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_measurement_sensors_unavailable_when_not_ready(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test measurements are unavailable before sensor data is ready."""
    await _setup_entry(hass, sensors={**TEST_SENSORS, "sensor_ready": False})

    temp_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-RAM-0001_temperature_c"
    )
    assert temp_entity is not None
    assert hass.states.get(temp_entity).state == STATE_UNAVAILABLE
