"""Test area_registry API."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_unordered import unordered

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.config import area_registry
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.util.dt import utcnow

from tests.common import ANY
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(name="client")
async def client_fixture(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    area_registry.async_setup(hass)
    return await hass_ws_client(hass)


@pytest.fixture
async def mock_temperature_humidity_entity(hass: HomeAssistant) -> None:
    """Mock temperature and humidity sensors."""
    hass.states.async_set(
        "sensor.mock_temperature",
        "20",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    hass.states.async_set(
        "sensor.mock_humidity",
        "50",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )
    hass.states.async_set(
        "binary_sensor.mock_motion",
        "off",
        {
            ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION,
        },
    )


async def test_list_areas(
    client: MockHAClientWebSocket,
    area_registry: ar.AreaRegistry,
    freezer: FrozenDateTimeFactory,
    mock_temperature_humidity_entity: None,
) -> None:
    """Test list entries."""
    created_area1 = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_area1)
    area1 = area_registry.async_create("mock 1")

    created_area2 = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(created_area2)
    area2 = area_registry.async_create(
        "mock 2",
        aliases={"alias_1", "alias_2"},
        floor_id="first_floor",
        humidity_entity_id="sensor.mock_humidity",
        icon="mdi:garage",
        labels={"label_1", "label_2"},
        motion_entity_id="binary_sensor.mock_motion",
        picture="/image/example.png",
        temperature_entity_id="sensor.mock_temperature",
    )

    await client.send_json_auto_id({"type": "config/area_registry/list"})

    msg = await client.receive_json()
    assert msg["result"] == [
        {
            "aliases": [],
            "area_id": area1.id,
            "created_at": created_area1.timestamp(),
            "floor_id": None,
            "humidity_entity_id": None,
            "icon": None,
            "labels": [],
            "modified_at": created_area1.timestamp(),
            "name": "mock 1",
            "picture": None,
            "temperature_entity_id": None,
            "motion_entity_id": None,
        },
        {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": area2.id,
            "created_at": created_area2.timestamp(),
            "floor_id": "first_floor",
            "humidity_entity_id": "sensor.mock_humidity",
            "icon": "mdi:garage",
            "labels": unordered(["label_1", "label_2"]),
            "modified_at": created_area2.timestamp(),
            "motion_entity_id": "binary_sensor.mock_motion",
            "name": "mock 2",
            "picture": "/image/example.png",
            "temperature_entity_id": "sensor.mock_temperature",
        },
    ]


async def test_create_area(
    client: MockHAClientWebSocket,
    area_registry: ar.AreaRegistry,
    freezer: FrozenDateTimeFactory,
    mock_temperature_humidity_entity: None,
) -> None:
    """Test create entry."""
    # Create area with only mandatory parameters
    await client.send_json_auto_id(
        {"name": "mock", "type": "config/area_registry/create"}
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": [],
        "area_id": ANY,
        "floor_id": None,
        "icon": None,
        "labels": [],
        "name": "mock",
        "picture": None,
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
        "temperature_entity_id": None,
        "humidity_entity_id": None,
        "motion_entity_id": None,
    }
    assert len(area_registry.areas) == 1

    # Create area with all parameters
    await client.send_json_auto_id(
        {
            "aliases": ["alias_1", "alias_2"],
            "floor_id": "first_floor",
            "icon": "mdi:garage",
            "labels": ["label_1", "label_2"],
            "name": "mock 2",
            "picture": "/image/example.png",
            "temperature_entity_id": "sensor.mock_temperature",
            "humidity_entity_id": "sensor.mock_humidity",
            "motion_entity_id": "binary_sensor.mock_motion",
            "type": "config/area_registry/create",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "aliases": unordered(["alias_1", "alias_2"]),
        "area_id": ANY,
        "floor_id": "first_floor",
        "icon": "mdi:garage",
        "labels": unordered(["label_1", "label_2"]),
        "name": "mock 2",
        "picture": "/image/example.png",
        "created_at": utcnow().timestamp(),
        "modified_at": utcnow().timestamp(),
        "temperature_entity_id": "sensor.mock_temperature",
        "humidity_entity_id": "sensor.mock_humidity",
        "motion_entity_id": "binary_sensor.mock_motion",
    }
    assert len(area_registry.areas) == 2


async def test_create_area_with_name_already_in_use(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test create entry that should fail."""
    area_registry.async_create("mock")

    await client.send_json_auto_id(
        {"name": "mock", "type": "config/area_registry/create"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock (mock) is already in use"
    assert len(area_registry.areas) == 1


async def test_delete_area(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test delete entry."""
    area = area_registry.async_create("mock")

    await client.send_json(
        {"id": 1, "area_id": area.id, "type": "config/area_registry/delete"}
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert not area_registry.areas


async def test_delete_non_existing_area(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test delete entry that should fail."""
    area_registry.async_create("mock")

    await client.send_json_auto_id(
        {"area_id": "", "type": "config/area_registry/delete"}
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "Area ID doesn't exist"
    assert len(area_registry.areas) == 1


async def test_update_area(
    client: MockHAClientWebSocket,
    area_registry: ar.AreaRegistry,
    freezer: FrozenDateTimeFactory,
    mock_temperature_humidity_entity: None,
) -> None:
    """Test update entry."""
    created_at = datetime.fromisoformat("2024-07-16T13:30:00.900075+00:00")
    freezer.move_to(created_at)
    area = area_registry.async_create("mock 1")
    modified_at = datetime.fromisoformat("2024-07-16T13:45:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "type": "config/area_registry/update",
            "aliases": ["alias_1", "alias_2"],
            "area_id": area.id,
            "floor_id": "first_floor",
            "humidity_entity_id": "sensor.mock_humidity",
            "icon": "mdi:garage",
            "labels": ["label_1", "label_2"],
            "motion_entity_id": "binary_sensor.mock_motion",
            "name": "mock 2",
            "picture": "/image/example.png",
            "temperature_entity_id": "sensor.mock_temperature",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": unordered(["alias_1", "alias_2"]),
        "area_id": area.id,
        "floor_id": "first_floor",
        "humidity_entity_id": "sensor.mock_humidity",
        "icon": "mdi:garage",
        "labels": unordered(["label_1", "label_2"]),
        "motion_entity_id": "binary_sensor.mock_motion",
        "name": "mock 2",
        "picture": "/image/example.png",
        "temperature_entity_id": "sensor.mock_temperature",
        "created_at": created_at.timestamp(),
        "modified_at": modified_at.timestamp(),
    }
    assert len(area_registry.areas) == 1

    modified_at = datetime.fromisoformat("2024-07-16T13:50:00.900075+00:00")
    freezer.move_to(modified_at)

    await client.send_json_auto_id(
        {
            "type": "config/area_registry/update",
            "aliases": ["alias_1", "alias_1"],
            "area_id": area.id,
            "floor_id": None,
            "humidity_entity_id": None,
            "icon": None,
            "labels": [],
            "motion_entity_id": None,
            "picture": None,
            "temperature_entity_id": None,
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": ["alias_1"],
        "area_id": area.id,
        "floor_id": None,
        "icon": None,
        "labels": [],
        "name": "mock 2",
        "picture": None,
        "temperature_entity_id": None,
        "humidity_entity_id": None,
        "motion_entity_id": None,
        "created_at": created_at.timestamp(),
        "modified_at": modified_at.timestamp(),
    }
    assert len(area_registry.areas) == 1


async def test_update_area_with_same_name(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")

    await client.send_json_auto_id(
        {
            "area_id": area.id,
            "name": "mock 1",
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"]["area_id"] == area.id
    assert msg["result"]["name"] == "mock 1"
    assert len(area_registry.areas) == 1


async def test_update_area_with_name_already_in_use(
    client: MockHAClientWebSocket, area_registry: ar.AreaRegistry
) -> None:
    """Test update entry."""
    area = area_registry.async_create("mock 1")
    area_registry.async_create("mock 2")

    await client.send_json_auto_id(
        {
            "area_id": area.id,
            "name": "mock 2",
            "type": "config/area_registry/update",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_info"
    assert msg["error"]["message"] == "The name mock 2 (mock2) is already in use"
    assert len(area_registry.areas) == 2
