"""Test DROP binary sensor entities."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
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
    config_entry_hub,
    config_entry_leak,
    config_entry_protection_valve,
    config_entry_pump_controller,
    config_entry_ro_filter,
    config_entry_softener,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.mark.parametrize(
    ("config_entry", "topic", "reset", "data"),
    [
        (config_entry_hub(), TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET, TEST_DATA_HUB),
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
        "leak",
        "softener",
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

    with patch(
        "homeassistant.components.drop_connect.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id).state == STATE_OFF

    async_fire_mqtt_message(hass, topic, reset)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id).state == STATE_OFF

    async_fire_mqtt_message(hass, topic, data)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )
