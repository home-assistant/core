"""Test DROP sensor entities."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
