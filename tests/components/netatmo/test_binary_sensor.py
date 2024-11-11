"""Support for Netatmo binary sensors."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.netatmo.const import NETATMO_EVENT
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import selected_platforms, simulate_webhook, snapshot_platform_entities

from tests.common import MockConfigEntry, async_capture_events


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.BINARY_SENSOR,
        entity_registry,
        snapshot,
    )


async def test_webhook_siren_event(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test that person events are handled."""
    with selected_platforms([Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    test_netatmo_event = async_capture_events(hass, NETATMO_EVENT)
    assert not test_netatmo_event

    fake_webhook_event = {
        "event_type": "home_alarm",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:e3",
        "event_id": "1234567890",
        "message": "Update Siren",
        "push_type": "NACamerahome_alarm",
    }

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, fake_webhook_event)
    assert test_netatmo_event


async def test_webhook_opening_event(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test window events are handled."""
    with selected_platforms([Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.window_hall_window").state == "off"
    test_netatmo_event = async_capture_events(hass, NETATMO_EVENT)
    assert not test_netatmo_event

    fake_webhook_event = {
        "event_type": "tag_open",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:86:99",
        "event_id": "1234567890",
        "message": "Window open",
        "push_type": "NACamera-tag_open",
    }

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    await simulate_webhook(hass, webhook_id, fake_webhook_event)
    assert hass.states.get("binary_sensor.window_hall_window").state == "on"

    assert test_netatmo_event
