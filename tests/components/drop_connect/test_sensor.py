"""Test DROP sensor entities."""

from collections.abc import Callable, Generator
from dataclasses import dataclass
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.drop_connect.const import (
    CONF_DEVICE_DESC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
)
from homeassistant.components.drop_connect.sensor import WATER_USED_TODAY, DROPSensor
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityDescription

from .common import (
    TEST_DATA_ALERT,
    TEST_DATA_ALERT_RESET,
    TEST_DATA_ALERT_TOPIC,
    TEST_DATA_FILTER,
    TEST_DATA_FILTER_RESET,
    TEST_DATA_FILTER_TOPIC,
    TEST_DATA_HUB,
    TEST_DATA_HUB_RESET,
    TEST_DATA_HUB_TOPIC,
    TEST_DATA_LEAK,
    TEST_DATA_LEAK_RESET,
    TEST_DATA_LEAK_TOPIC,
    TEST_DATA_PROTECTION_VALVE,
    TEST_DATA_PROTECTION_VALVE_RESET,
    TEST_DATA_PROTECTION_VALVE_TOPIC,
    TEST_DATA_PUMP_CONTROLLER,
    TEST_DATA_PUMP_CONTROLLER_RESET,
    TEST_DATA_PUMP_CONTROLLER_TOPIC,
    TEST_DATA_RO_FILTER,
    TEST_DATA_RO_FILTER_RESET,
    TEST_DATA_RO_FILTER_TOPIC,
    TEST_DATA_SOFTENER,
    TEST_DATA_SOFTENER_RESET,
    TEST_DATA_SOFTENER_TOPIC,
    config_entry_alert,
    config_entry_filter,
    config_entry_hub,
    config_entry_leak,
    config_entry_protection_valve,
    config_entry_pump_controller,
    config_entry_ro_filter,
    config_entry_softener,
    help_assert_entries,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.fixture(autouse=True)
def only_sensor_platform() -> Generator[None]:
    """Only setup the DROP sensor platform."""
    with patch("homeassistant.components.drop_connect.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.parametrize(
    ("config_entry", "topic", "reset", "data"),
    [
        (config_entry_hub(), TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET, TEST_DATA_HUB),
        (
            config_entry_alert(),
            TEST_DATA_ALERT_TOPIC,
            TEST_DATA_ALERT_RESET,
            TEST_DATA_ALERT,
        ),
        (
            config_entry_leak(),
            TEST_DATA_LEAK_TOPIC,
            TEST_DATA_LEAK_RESET,
            TEST_DATA_LEAK,
        ),
        (
            config_entry_softener(),
            TEST_DATA_SOFTENER_TOPIC,
            TEST_DATA_SOFTENER_RESET,
            TEST_DATA_SOFTENER,
        ),
        (
            config_entry_filter(),
            TEST_DATA_FILTER_TOPIC,
            TEST_DATA_FILTER_RESET,
            TEST_DATA_FILTER,
        ),
        (
            config_entry_protection_valve(),
            TEST_DATA_PROTECTION_VALVE_TOPIC,
            TEST_DATA_PROTECTION_VALVE_RESET,
            TEST_DATA_PROTECTION_VALVE,
        ),
        (
            config_entry_pump_controller(),
            TEST_DATA_PUMP_CONTROLLER_TOPIC,
            TEST_DATA_PUMP_CONTROLLER_RESET,
            TEST_DATA_PUMP_CONTROLLER,
        ),
        (
            config_entry_ro_filter(),
            TEST_DATA_RO_FILTER_TOPIC,
            TEST_DATA_RO_FILTER_RESET,
            TEST_DATA_RO_FILTER,
        ),
    ],
    ids=[
        "hub",
        "alert",
        "leak",
        "softener",
        "filter",
        "protection_valve",
        "pump_controller",
        "ro_filter",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    topic: str,
    reset: str,
    data: str,
) -> None:
    """Test DROP sensors."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    help_assert_entries(hass, entity_registry, snapshot, config_entry, "init", True)

    async_fire_mqtt_message(hass, topic, reset)
    await hass.async_block_till_done()
    help_assert_entries(hass, entity_registry, snapshot, config_entry, "reset")

    async_fire_mqtt_message(hass, topic, data)
    await hass.async_block_till_done()
    help_assert_entries(hass, entity_registry, snapshot, config_entry, "data")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for testing."""
    return MockConfigEntry(
        domain="drop_connect",
        unique_id="test_device_id",
        data={
            CONF_DEVICE_DESC: "Hub",
            CONF_DEVICE_TYPE: "hub",
            CONF_HUB_ID: "test_hub_id",
            CONF_DEVICE_NAME: "Test Hub",
        },
    )


@pytest.fixture
def mock_coordinator(mock_config_entry):
    """Mock a coordinator for sensor tests."""

    class MockCoordinator:
        def __init__(self) -> None:
            self.data = {}
            self.config_entry = mock_config_entry

    return MockCoordinator()


@dataclass
class DummySensorEntityDescription(EntityDescription):
    """A minimal sensor entity description for testing."""

    state_class: SensorStateClass | None = None
    value_fn: Callable | None = None


@pytest.fixture
def mock_description():
    """Mock a sensor description for water_used_today tests."""
    return DummySensorEntityDescription(
        key=WATER_USED_TODAY,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.data.get("usedToday", 0),
    )


def test_water_used_today(mock_coordinator, mock_description) -> None:
    """Test handling of water_used_today sensor values."""

    sensor = DROPSensor(mock_coordinator, mock_description)

    # Simulate a normal reading at 9 AM
    mock_coordinator.data = {"usedToday": 1100}
    with freeze_time("2025-07-15 09:00:00"):
        assert sensor.native_value == 1100

    # Simulate a glitch: drop to 0 at 9:01 AM
    mock_coordinator.data = {"usedToday": 0}
    with freeze_time("2025-07-15 09:01:00"):
        assert sensor.native_value == 1100  # should return previous value

    # Simulate legitimate reset at 12:03 AM (within 10-min window)
    mock_coordinator.data = {"usedToday": 0}
    with freeze_time("2025-07-16 00:03:00"):
        assert sensor.native_value == 0  # allow legitimate reset

    # After reset, new usage comes in
    mock_coordinator.data = {"usedToday": 5}
    with freeze_time("2025-07-16 00:10:00"):
        assert sensor.native_value == 5
