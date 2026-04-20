"""Tests for the Huawei LTE SMS event entity and Last SMS sensor."""

from unittest.mock import MagicMock, patch

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import magic_client

from tests.common import MockConfigEntry

MOCK_CONF_URL = "http://huawei-lte.example.com"


async def _setup_integration(
    hass: HomeAssistant,
    enable_last_sms: bool = False,
) -> tuple[MockConfigEntry, MagicMock]:
    """Set up the integration with a mock client."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: MOCK_CONF_URL})
    entry.add_to_hass(hass)
    client = magic_client()
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    if enable_last_sms:
        ent_reg = er.async_get(hass)
        ent_entry = ent_reg.async_get("sensor.test_router_last_sms")
        if ent_entry and ent_entry.disabled:
            ent_reg.async_update_entity("sensor.test_router_last_sms", disabled_by=None)
            with (
                patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
                patch(
                    "homeassistant.components.huawei_lte.Client",
                    return_value=client,
                ),
            ):
                await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()

    return entry, client


async def test_sms_event_entity_exists(hass: HomeAssistant) -> None:
    """Test that the SMS received event entity is created."""
    await _setup_integration(hass)

    state = hass.states.get("event.test_router_sms_received")
    assert state is not None


async def test_initial_scan_no_event_fired(hass: HomeAssistant) -> None:
    """Test that initial SMS scan does not trigger the event entity."""
    await _setup_integration(hass)
    await hass.async_block_till_done()

    state = hass.states.get("event.test_router_sms_received")
    assert state is not None
    # No event fired yet — state should be None (no last event timestamp)
    assert state.state == "unknown"


async def test_new_sms_fires_event_entity(hass: HomeAssistant) -> None:
    """Test that a new SMS on subsequent scan triggers the event entity."""
    entry, client = await _setup_integration(hass)
    await hass.async_block_till_done()

    state = hass.states.get("event.test_router_sms_received")
    assert state is not None
    assert state.state == "unknown"

    # Simulate a new message appearing on next poll
    client.sms.get_sms_list.return_value = {
        "Count": "3",
        "Messages": {
            "Message": [
                {
                    "Smstat": "0",
                    "Index": "40001",
                    "Phone": "+1234567890",
                    "Content": "Test message 1",
                    "Date": "2026-03-29 10:00:00",
                },
                {
                    "Smstat": "1",
                    "Index": "40002",
                    "Phone": "+0987654321",
                    "Content": "Test message 2",
                    "Date": "2026-03-29 09:00:00",
                },
                {
                    "Smstat": "0",
                    "Index": "40003",
                    "Phone": "+5551234567",
                    "Content": "New message!",
                    "Date": "2026-03-29 11:00:00",
                },
            ]
        },
    }

    # Trigger another update
    router = hass.data[DOMAIN].routers[entry.entry_id]
    await hass.async_add_executor_job(router.update)
    await hass.async_block_till_done()

    state = hass.states.get("event.test_router_sms_received")
    assert state is not None
    # Event entity should now have a timestamp (not unknown)
    assert state.state != "unknown"
    # Check event attributes
    assert state.attributes["event_type"] == "sms_received"
    assert state.attributes["phone"] == "+5551234567"
    assert state.attributes["content"] == "New message!"
    assert state.attributes["index"] == 40003


async def test_last_sms_sensor(hass: HomeAssistant) -> None:
    """Test Last SMS sensor shows latest message content."""
    await _setup_integration(hass, enable_last_sms=True)

    state = hass.states.get("sensor.test_router_last_sms")
    assert state is not None
    assert state.state == "Test message 1"
    assert state.attributes["phone"] == "+1234567890"
    assert state.attributes["index"] == 40001
    assert state.attributes["read"] is False


async def test_last_sms_sensor_updates(hass: HomeAssistant) -> None:
    """Test Last SMS sensor updates when new message arrives."""
    entry, client = await _setup_integration(hass, enable_last_sms=True)

    client.sms.get_sms_list.return_value = {
        "Count": "1",
        "Messages": {
            "Message": {
                "Smstat": "0",
                "Index": "40005",
                "Phone": "+9999999999",
                "Content": "Brand new message",
                "Date": "2026-03-29 12:00:00",
            }
        },
    }

    router = hass.data[DOMAIN].routers[entry.entry_id]
    await hass.async_add_executor_job(router.update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_router_last_sms")
    assert state.state == "Brand new message"
    assert state.attributes["phone"] == "+9999999999"
    assert state.attributes["index"] == 40005


async def test_last_sms_sensor_empty(hass: HomeAssistant) -> None:
    """Test Last SMS sensor handles empty inbox."""
    entry, client = await _setup_integration(hass, enable_last_sms=True)

    client.sms.get_sms_list.return_value = {"Count": "0", "Messages": None}

    router = hass.data[DOMAIN].routers[entry.entry_id]
    await hass.async_add_executor_job(router.update)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_router_last_sms")
    assert state is not None
    assert state.state == "unknown"
