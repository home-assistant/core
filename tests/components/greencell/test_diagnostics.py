"""Tests for the Greencell diagnostics."""

from pytest_homeassistant.common import MockConfigEntry, async_fire_mqtt_message
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_CURRENT_PAYLOAD_3PHASE,
    TEST_CURRENT_TOPIC,
    TEST_POWER_PAYLOAD_CHARGING,
    TEST_POWER_TOPIC,
    TEST_STATUS_PAYLOAD_CHARGING,
    TEST_STATUS_TOPIC,
    TEST_VOLTAGE_PAYLOAD_NORMAL,
    TEST_VOLTAGE_TOPIC,
)


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    async_fire_mqtt_message(hass, TEST_CURRENT_TOPIC, TEST_CURRENT_PAYLOAD_3PHASE)
    async_fire_mqtt_message(hass, TEST_VOLTAGE_TOPIC, TEST_VOLTAGE_PAYLOAD_NORMAL)
    async_fire_mqtt_message(hass, TEST_POWER_TOPIC, TEST_POWER_PAYLOAD_CHARGING)
    async_fire_mqtt_message(hass, TEST_STATUS_TOPIC, TEST_STATUS_PAYLOAD_CHARGING)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, setup_integration)
        == snapshot
    )
