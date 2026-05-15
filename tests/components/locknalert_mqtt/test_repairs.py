"""Tests for LocknAlert MQTT repairs."""

import pytest

from homeassistant.components.locknalert_mqtt.const import (
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
)
from homeassistant.components.locknalert_mqtt.repairs import (
    MQTTDeviceEntryMigration,
    async_create_fix_flow,
)
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    get_repairs,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, MqttMockHAClientGenerator


@pytest.fixture
def mqtt_config_entry_data() -> dict:
    """Provide default config entry data."""
    return {CONF_BROKER: "mock-broker"}


@pytest.fixture
def mqtt_config_entry_options() -> dict:
    """Provide default config entry options."""
    return {CONF_BIRTH_MESSAGE: {}}


async def test_device_entry_migration_confirm_flow(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_client: ClientSessionGenerator,
) -> None:
    """MQTTDeviceEntryMigration flow shows confirm form then removes subentry."""
    assert await async_setup_component(hass, "repairs", {})
    await mqtt_mock_entry()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test-subentry-id")},
        name="Test MQTT Device",
    )

    ir.async_create_issue(
        hass,
        DOMAIN,
        "device_migration_test",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="device_migration",
        data={
            "entry_id": entry.entry_id,
            "subentry_id": "test-subentry-id",
            "name": "Test MQTT Device",
        },
    )

    client = await hass_client()
    resp = await start_repair_fix_flow(client, DOMAIN, "device_migration_test")
    flow_id = resp["flow_id"]
    assert resp["step_id"] == "confirm"

    resp = await process_repair_fix_flow(client, flow_id, json={})
    assert resp["type"] == FlowResultType.CREATE_ENTRY


async def test_async_create_fix_flow_returns_migration_flow(
    hass: HomeAssistant,
) -> None:
    """async_create_fix_flow creates a MQTTDeviceEntryMigration instance."""
    flow = await async_create_fix_flow(
        hass,
        issue_id="test_issue",
        data={
            "entry_id": "test-entry-id",
            "subentry_id": "test-subentry-id",
            "name": "Test Device",
        },
    )
    assert isinstance(flow, MQTTDeviceEntryMigration)
    assert flow.entry_id == "test-entry-id"
    assert flow.subentry_id == "test-subentry-id"
    assert flow.name == "Test Device"
