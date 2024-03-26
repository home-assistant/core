"""The tests for the Netatmo sensor platform."""
from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import selected_platforms, simulate_webhook, snapshot_platform_entities

from tests.common import MockConfigEntry


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


async def test_window_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test weather sensor setup."""
    with selected_platforms([Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    prefix = "binary_sensor.window_hall_"
    assert hass.states.get(f"{prefix}opening").state == "off"
    assert hass.states.get(f"{prefix}motion").state == "off"
    assert hass.states.get(f"{prefix}vibration").state == "off"

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Fake backend response
    response = {
        "event_type": "tag_small_move",
        "push_type": "NACamera-tag_small_move",
        "home_id": "3d3e344f491763b24c424e8b",
        "event_id": "601dce1560abca1ebad9b723",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:86:99",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}opening").state == "off"
    assert hass.states.get(f"{prefix}motion").state == "off"
    assert hass.states.get(f"{prefix}vibration").state == "on"

    # Fake backend response
    response = {
        "event_type": "tag_big_move",
        "push_type": "NACamera-tag_big_move",
        "home_id": "3d3e344f491763b24c424e8b",
        "event_id": "601dce1560abca1ebad9b723",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:86:99",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}opening").state == "off"
    assert hass.states.get(f"{prefix}motion").state == "on"
    assert hass.states.get(f"{prefix}vibration").state == "off"

    response = {
        "event_type": "tag_open",
        "push_type": "NACamera-tag_open",
        "home_id": "3d3e344f491763b24c424e8b",
        "event_id": "601dce1560abca1ebad9b723",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:86:99",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}opening").state == "on"
    assert hass.states.get(f"{prefix}motion").state == "off"
    assert hass.states.get(f"{prefix}vibration").state == "off"

    # Fake backend response
    response = {
        "event_type": "tag_big_move",
        "push_type": "NACamera-tag_big_move",
        "home_id": "3d3e344f491763b24c424e8b",
        "event_id": "601dce1560abca1ebad9b723",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:86:99",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}opening").state == "on"
    assert hass.states.get(f"{prefix}motion").state == "on"
    assert hass.states.get(f"{prefix}vibration").state == "off"

    # Fake backend response
    response = {
        "event_type": "tag_uninstalled",
        "push_type": "NACamera-tag_uninstalled",
        "home_id": "3d3e344f491763b24c424e8b",
        "event_id": "601dce1560abca1ebad9b723",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:f1:62",
        "module_id": "12:34:56:00:86:99",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}opening").state == "unavailable"
    assert hass.states.get(f"{prefix}motion").state == "unavailable"
    assert hass.states.get(f"{prefix}vibration").state == "unavailable"


async def test_siren_sensor(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test weather sensor setup."""
    with selected_platforms([Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    prefix = "binary_sensor.sirene_in_hall_"
    assert hass.states.get(f"{prefix}monitoring").state == "on"
    assert hass.states.get(f"{prefix}sounding").state == "off"

    webhook_id = config_entry.data[CONF_WEBHOOK_ID]

    # Fake backend response changing schedule
    response = {
        "event_type": "home_alarm",
        "push_type": "NACamera-home_alarm",
        "home_id": "3d3e344f491763b24c424e8b",
        "event_id": "601dce1560abca1ebad9b723",
        "camera_id": "12:34:56:00:f1:62",
        "device_id": "12:34:56:00:e3:9b",
    }
    await simulate_webhook(hass, webhook_id, response)
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}monitoring").state == "on"
    assert hass.states.get(f"{prefix}sounding").state == "off"
