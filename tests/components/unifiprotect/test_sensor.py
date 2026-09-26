"""Test the UniFi Protect sensor platform."""

from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from uiprotect.data import (
    NVR,
    AiPort,
    Camera,
    DeviceState,
    Event,
    EventType,
    Light,
    ModelType,
    Sensor,
    WSAction,
)
from uiprotect.data.nvr import EventMetadata
from uiprotect.data.public_devices import SensorFeatureCapability
from uiprotect.utils import convert_to_datetime, to_js_time
from uiprotect.websocket import WebsocketState

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION, DOMAIN
from homeassistant.components.unifiprotect.sensor import (
    ALL_DEVICES_SENSORS,
    CAMERA_DISABLED_SENSORS,
    CAMERA_SENSORS,
    LIGHT_SENSORS,
    MOTION_TRIP_SENSORS,
    NVR_DISABLED_SENSORS,
    NVR_SENSORS,
    SENSE_SENSORS,
    ProtectSensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    ids_from_device_description,
    init_entry,
    make_public_camera,
    make_public_light,
    make_public_sensor,
    public_device_ws_message,
    remove_entities,
    reset_objects,
    setup_public_light,
    setup_public_sensor,
    time_changed,
)


def get_sensor_by_key(sensors: tuple, key: str) -> ProtectSensorEntityDescription:
    """Get sensor description by key."""
    for sensor in sensors:
        if sensor.key == key:
            return sensor
    raise ValueError(f"Sensor with key '{key}' not found")


# Constants for test slicing (subsets of sensor tuples)
CAMERA_SENSORS_WRITE = CAMERA_SENSORS[:5]
SENSE_SENSORS_WRITE = SENSE_SENSORS[:8]


async def test_sensor_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SENSOR, 24, 12)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SENSOR, 12, 9)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SENSOR, 24, 12)


async def test_sensor_sensor_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)
    await remove_entities(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 12, 9)
    await adopt_devices(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)


async def test_sensor_sense_capability_creation_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A capability map limits sensor entity creation to the advertised capabilities."""
    setup_public_sensor(
        ufp,
        capabilities={SensorFeatureCapability.OPEN, SensorFeatureCapability.TAMPER},
    )
    await init_entry(hass, ufp, [sensor_all])

    for key, created in (
        ("battery_level", True),
        ("door_last_trip_time", True),
        ("tampering_last_trip_time", True),
        ("temperature_level", False),
        ("humidity_level", False),
        ("light_level", False),
        ("alarm_sound", False),
        ("motion_last_trip_time", False),
    ):
        description = next(d for d in SENSE_SENSORS if d.key == key)
        _, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, sensor_all, description
        )
        assert (entity_registry.async_get(entity_id) is not None) is created, key


async def test_sensor_sense_metrics_read_their_own_public_path(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Each environmental sensor reads its own metric from the public object.

    The fixture reports the same number for light, humidity and temperature, so
    a swapped ``ufp_public_value`` path would go unnoticed without diverging
    values here.
    """
    setup_public_sensor(
        ufp, light_value=11.0, humidity_value=22.0, temperature_value=33.0
    )
    await init_entry(hass, ufp, [sensor_all])

    name = sensor_all.name.lower().replace(" ", "_")
    assert hass.states.get(f"sensor.{name}_illuminance").state == "11.0"
    assert hass.states.get(f"sensor.{name}_humidity").state == "22.0"
    assert hass.states.get(f"sensor.{name}_temperature").state == "33.0"


async def test_sensor_setup_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Test sensor entity setup for sensor devices."""

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    expected_values = (
        "10",
        "10.0",
        "10.0",
        "10.0",
        "none",
    )
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        if not description.entity_registry_enabled_default:
            continue
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, sensor_all, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # BLE signal
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(ALL_DEVICES_SENSORS, "ble_signal"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "-50"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_sensor_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor: Sensor,
) -> None:
    """Test sensor entity setup for sensor devices with no sensors enabled."""

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    expected_values = (
        "10",
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
    )
    for index, description in enumerate(SENSE_SENSORS_WRITE):
        if not description.entity_registry_enabled_default:
            continue
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, sensor, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_battery_public_ws_update(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Battery level refreshes from a public devices WS update."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[0]
    )
    assert hass.states.get(entity_id).state == "10"

    public = make_public_sensor(sensor_all, percentage=42)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "42"


async def test_sensor_battery_unavailable_on_public_disconnect(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Battery availability follows the public object's connection state."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[0]
    )
    assert hass.states.get(entity_id).state == "10"

    public = make_public_sensor(sensor_all, state=DeviceState.DISCONNECTED)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensor_battery_unavailable_without_public_api(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A migrated battery entity is unavailable without a public object."""
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[0]
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensor_battery_unavailable_on_public_ws_disconnect(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Battery follows the public websocket health, not the private one."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[0]
    )
    assert hass.states.get(entity_id).state == "10"

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensor_battery_refreshes_on_public_ws_reconnect(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Battery re-reads the bootstrap on public websocket reconnect."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, sensor_all, SENSE_SENSORS_WRITE[0]
    )
    assert hass.states.get(entity_id).state == "10"

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Value changes while the socket is down; the bootstrap holds the new value.
    sensor_all.battery_status.percentage = 55
    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "55"


async def test_sensor_setup_nvr(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    fixed_now: datetime,
) -> None:
    """Test sensor entity setup for NVR device."""

    reset_objects(ufp.api.bootstrap)
    nvr: NVR = ufp.api.bootstrap.nvr
    nvr.up_since = fixed_now
    nvr.system_info.cpu.average_load = 50.0
    nvr.system_info.cpu.temperature = 50.0
    nvr.storage_stats.utilization = 50.0
    nvr.system_info.memory.available = 50.0
    nvr.system_info.memory.total = 100.0
    nvr.storage_stats.storage_distribution.timelapse_recordings.percentage = 50.0
    nvr.storage_stats.storage_distribution.continuous_recordings.percentage = 50.0
    nvr.storage_stats.storage_distribution.detections_recordings.percentage = 50.0
    nvr.storage_stats.storage_distribution.hd_usage.percentage = 50.0
    nvr.storage_stats.storage_distribution.uhd_usage.percentage = 50.0
    nvr.storage_stats.storage_distribution.free.percentage = 50.0
    nvr.storage_stats.capacity = 50.0

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SENSOR, 12, 9)

    expected_values = (
        fixed_now.replace(second=0, microsecond=0).isoformat(),
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50.0",
        "50",
    )
    for index, description in enumerate(NVR_SENSORS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, nvr, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        if not description.entity_registry_enabled_default:
            await enable_entity(hass, ufp.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    expected_values = ("50.0", "50.0", "50.0")
    for index, description in enumerate(NVR_DISABLED_SENSORS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, nvr, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        await enable_entity(hass, ufp.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_nvr_missing_values(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, ufp: MockUFPFixture
) -> None:
    """Test NVR sensor sensors if no data available."""

    reset_objects(ufp.api.bootstrap)
    nvr: NVR = ufp.api.bootstrap.nvr
    nvr.system_info.memory.available = None
    nvr.system_info.memory.total = None
    nvr.up_since = None
    nvr.storage_stats.capacity = None

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.SENSOR, 12, 9)

    # Uptime
    description = get_sensor_by_key(NVR_SENSORS, "uptime")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Recording capacity
    description = get_sensor_by_key(NVR_SENSORS, "record_capacity")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Memory utilization
    description = get_sensor_by_key(NVR_DISABLED_SENSORS, "memory_utilization")
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_setup_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    fixed_now: datetime,
) -> None:
    """Test sensor entity setup for camera devices."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SENSOR, 24, 12)

    expected_values = (
        fixed_now.replace(microsecond=0).isoformat(),
        "0.0001",
        "0.0001",
        "20.0",
    )
    for index, description in enumerate(CAMERA_SENSORS_WRITE):
        if not description.entity_registry_enabled_default:
            continue
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, doorbell, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    expected_values = ("0.0001", "0.0001")
    for index, description in enumerate(CAMERA_DISABLED_SENSORS):
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SENSOR, doorbell, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.disabled is not description.entity_registry_enabled_default
        assert entity.unique_id == unique_id

        await enable_entity(hass, ufp.entry.entry_id, entity_id)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == expected_values[index]
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Wired signal (phy_rate / link speed)
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        doorbell,
        get_sensor_by_key(ALL_DEVICES_SENSORS, "phy_rate"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1000"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Wi-Fi signal
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        doorbell,
        get_sensor_by_key(ALL_DEVICES_SENSORS, "wifi_signal"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "-50"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup_camera_with_last_trip_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    fixed_now: datetime,
) -> None:
    """Test sensor entity setup for camera devices with last trip time."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SENSOR, 24, 24)

    # Last Trip Time
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        doorbell,
        get_sensor_by_key(MOTION_TRIP_SENSORS, "motion_last_trip_time"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.state
        == (fixed_now - timedelta(hours=1)).replace(microsecond=0).isoformat()
    )
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_sensor_update_alarm(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor, fixed_now: datetime
) -> None:
    """Test sensor motion entity."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)

    _, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(SENSE_SENSORS, "alarm_sound"),
    )

    event_metadata = EventMetadata(sensor_id=sensor_all.id, alarm_type="smoke")
    event = Event(
        model=ModelType.EVENT,
        id="test_event_id",
        type=EventType.SENSOR_ALARM,
        start=fixed_now - timedelta(seconds=1),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        metadata=event_metadata,
        api=ufp.api,
    )

    new_sensor = sensor_all.model_copy()
    new_sensor.set_alarm_timeout()
    new_sensor.last_alarm_event_id = event.id

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = event

    ufp.api.bootstrap.sensors = {new_sensor.id: new_sensor}
    ufp.api.bootstrap.events = {event.id: event}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "smoke"
    await time_changed(hass, 10)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_update_alarm_with_last_trip_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    fixed_now: datetime,
) -> None:
    """Test sensor motion entity with last trip time."""

    setup_public_sensor(ufp, tampering_detected_at=fixed_now - timedelta(hours=3))
    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 22)

    # Last Trip Time
    unique_id, entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(SENSE_SENSORS, "door_last_trip_time"),
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert (
        state.state
        == (fixed_now - timedelta(hours=2)).replace(microsecond=0).isoformat()
    )
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    # Door and motion map to different public fields; asserting both with
    # different offsets is what catches a swapped path.
    _, motion_entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(SENSE_SENSORS, "motion_last_trip_time"),
    )
    motion_state = hass.states.get(motion_entity_id)
    assert motion_state
    assert (
        motion_state.state
        == (fixed_now - timedelta(hours=1)).replace(microsecond=0).isoformat()
    )

    _, tamper_entity_id = await ids_from_device_description(
        hass,
        Platform.SENSOR,
        sensor_all,
        get_sensor_by_key(SENSE_SENSORS, "tampering_last_trip_time"),
    )
    tamper_state = hass.states.get(tamper_entity_id)
    assert tamper_state
    assert (
        tamper_state.state
        == (fixed_now - timedelta(hours=3)).replace(microsecond=0).isoformat()
    )


async def test_sensor_precision(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor, fixed_now: datetime
) -> None:
    """Test sensor precision value is respected."""

    await init_entry(hass, ufp, [sensor_all])
    assert_entity_counts(hass, Platform.SENSOR, 22, 14)
    nvr: NVR = ufp.api.bootstrap.nvr

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, nvr, get_sensor_by_key(NVR_SENSORS, "resolution_4K")
    )

    assert hass.states.get(entity_id).state == "17.49"


async def test_aiport_no_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    aiport: AiPort,
) -> None:
    """AI Port devices create no entities (support dropped)."""
    await init_entry(hass, ufp, [aiport])

    entities = er.async_entries_for_config_entry(entity_registry, ufp.entry.entry_id)
    assert not [e for e in entities if e.unique_id.startswith(f"{aiport.mac}_")]

    # Check no camera-specific sensors like motion detection exist
    for entity in entities:
        if entity.domain == Platform.SENSOR:
            # Camera-specific sensors should not exist for AI Port
            assert "detected_object" not in entity.unique_id
            assert "last_motion" not in entity.unique_id


async def test_aiport_no_sensor_entities_on_runtime_adopt(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    aiport: AiPort,
) -> None:
    """An AI Port adopted while running still creates no entities."""
    await init_entry(hass, ufp, [sensor_all])

    aiport._api = ufp.api
    aiport.feature_flags = Mock(is_ptz=False)
    await adopt_devices(hass, ufp, [aiport])

    entities = er.async_entries_for_config_entry(entity_registry, ufp.entry.entry_id)
    assert not [e for e in entities if e.unique_id.startswith(f"{aiport.mac}_")]


async def test_sensor_light_last_motion_public(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """The light's last-motion timestamp reads from the public API."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, light, LIGHT_SENSORS[0]
    )
    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    # A value the private fixture would not produce proves the public source.
    last_motion_ms = 1700000000000
    public = make_public_light(light, last_motion_ms=last_motion_ms)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert (
        hass.states.get(entity_id).state
        == convert_to_datetime(last_motion_ms).isoformat()
    )


async def test_sensor_light_last_motion_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """The migrated last-motion sensor is unavailable without a public object."""

    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SENSOR, light, LIGHT_SENSORS[0]
    )
    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


def _sensor_keys(entity_registry: er.EntityRegistry, mac: str) -> set[str]:
    """Return the description keys of the sensors registered for a device."""
    prefix = f"{mac}_"
    return {
        entry.unique_id.removeprefix(prefix)
        for entry in entity_registry.entities.values()
        if entry.domain == Platform.SENSOR and entry.unique_id.startswith(prefix)
    }


async def test_public_only_sensor_sense_end_to_end(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_all: Sensor,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A public-only entry builds the migrated sense sensors from the public object.

    The readings and trip timestamps follow the capability map; the private-only
    sensors (alarm sound, sensitivity, mount type, paired camera) are absent.
    """
    public = make_public_sensor(
        sensor_all,
        percentage=42,
        temperature_value=21.5,
        capabilities={
            SensorFeatureCapability.TEMPERATURE,
            SensorFeatureCapability.MOTION,
        },
    )
    ufp_public_only.api.public_bootstrap.sensors[sensor_all.id] = public

    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    keys = _sensor_keys(entity_registry, sensor_all.mac)
    assert {"battery_level", "temperature_level", "motion_last_trip_time"} <= keys
    assert not keys & {"alarm_sound", "sensitivity", "mount_type", "paired_camera"}
    assert "humidity_level" not in keys

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{sensor_all.mac}_battery_level"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == "42"


async def test_public_only_sensor_light_end_to_end(
    entity_registry: er.EntityRegistry,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A public-only entry builds the migrated floodlight sensor.

    ``paired_camera`` reads the private bootstrap, so it stays absent, and the
    read-only mirrors of the writable sensitivity and light mode are skipped
    because an API key can always write. The trip timestamp is disabled by
    default, like its private counterpart.
    """
    public = make_public_light(light, last_motion_ms=to_js_time(utcnow()))
    ufp_public_only.api.public_bootstrap.lights[light.id] = public

    await setup_public_only()

    keys = _sensor_keys(entity_registry, light.mac)
    assert "motion_last_trip_time" in keys
    assert not keys & {"paired_camera", "sensitivity", "light_motion"}

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{light.mac}_motion_last_trip_time"
    )
    assert entity_id
    assert (
        entity_registry.async_get(entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_public_only_sensor_camera_has_none(
    entity_registry: er.EntityRegistry,
    camera: Camera,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """The camera sensors all read the private bootstrap, so none are built."""
    public = make_public_camera(camera)
    public.rtsps_streams = None
    ufp_public_only.api.public_bootstrap.cameras[camera.id] = public

    await setup_public_only()

    assert _sensor_keys(entity_registry, camera.mac) == set()


async def test_public_only_sensor_added_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A light added later gets its sensors from its public add frame.

    The public devices websocket ``add`` frame is the only discovery signal
    without a local user; a re-delivered frame must not add a second time.
    """
    await setup_public_only()
    assert_entity_counts(hass, Platform.SENSOR, 0, 0)

    public = make_public_light(light)
    ufp_public_only.api.public_bootstrap.lights[light.id] = public
    msg = public_device_ws_message(public)
    msg.action = WSAction.ADD
    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert "motion_last_trip_time" in _sensor_keys(entity_registry, light.mac)
    count = len(hass.states.async_entity_ids(Platform.SENSOR.value))

    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(Platform.SENSOR.value)) == count
    assert "already exists" not in caplog.text
