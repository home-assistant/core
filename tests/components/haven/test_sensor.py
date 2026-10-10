"""Test HAVEN IAQ sensors."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from haveniaq import DeviceInfo, HavenApiError, SensorData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.haven.const import DOMAIN
from homeassistant.components.haven.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    TEST_CAM_INFO,
    TEST_CAM_SENSORS,
    TEST_CAM_SERIAL,
    TEST_SENSORS,
    TEST_SERIAL,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def mock_cam_haven_client(mock_haven_client: AsyncMock) -> None:
    """Configure the mocked client as a Central Air Monitor."""
    mock_haven_client.get_info.return_value = DeviceInfo.from_dict(TEST_CAM_INFO)
    mock_haven_client.get_sensors.return_value = SensorData.from_dict(TEST_CAM_SENSORS)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_haven_client")
async def test_ram_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test RAM entities and device metadata."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot(name="ram-device")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_cam_haven_client")
async def test_cam_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_cam_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test CAM-specific entities replace RAM-only entities."""
    await setup_integration(hass, mock_cam_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_cam_config_entry.entry_id
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_CAM_SERIAL), mock_cam_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot(name="cam-device")


@pytest.mark.usefixtures("mock_haven_client")
@pytest.mark.parametrize(
    "key",
    [
        "pm05_count_cm3",
        "pm1_count_cm3",
        "pm25_count_cm3",
        "pm4_count_cm3",
        "pm10_count_cm3",
    ],
)
async def test_particle_count_sensors_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
) -> None:
    """Test particle count sensors are disabled by default."""
    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{TEST_SERIAL}_{key}"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id) is None

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_measurement_sensors_unavailable_when_not_ready(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test measurements are unavailable before sensor data is ready."""
    mock_haven_client.get_sensors.return_value = SensorData.from_dict(
        {**TEST_SENSORS, "sensor_ready": False}
    )
    await setup_integration(hass, mock_config_entry)

    temp_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-RAM-0001_temperature_c"
    )
    assert temp_entity is not None
    temp_state = hass.states.get(temp_entity)
    assert temp_state is not None
    assert temp_state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_missing_measurement_is_unknown(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a missing measurement is unknown while the sensor remains ready."""
    mock_haven_client.get_sensors.return_value = SensorData.from_dict(
        {**TEST_SENSORS, "temperature_c": None}
    )
    await setup_integration(hass, mock_config_entry)

    temp_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-RAM-0001_temperature_c"
    )
    assert temp_entity is not None
    temp_state = hass.states.get(temp_entity)
    assert temp_state is not None
    assert temp_state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_unavailable_after_refresh_failure(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable after a refresh failure."""
    await setup_integration(hass, mock_config_entry)
    mock_haven_client.get_sensors.side_effect = HavenApiError("Unable to connect")

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    temp_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "TEST-RAM-0001_temperature_c"
    )
    assert temp_entity is not None
    temp_state = hass.states.get(temp_entity)
    assert temp_state is not None
    assert temp_state.state == STATE_UNAVAILABLE
