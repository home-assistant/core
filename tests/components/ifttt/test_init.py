"""Test the init file of IFTTT."""

from homeassistant import config_entries
from homeassistant.components import ifttt
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType

from tests.typing import ClientSessionGenerator


async def test_config_flow_registers_webhook(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test setting up IFTTT and sending webhook."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        "ifttt", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM, result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    webhook_id = result["result"].data["webhook_id"]

    ifttt_events = []

    @callback
    def handle_event(event):
        """Handle IFTTT event."""
        ifttt_events.append(event)

    hass.bus.async_listen(ifttt.EVENT_RECEIVED, handle_event)

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{webhook_id}", json={"hello": "ifttt"})

    assert len(ifttt_events) == 1
    assert ifttt_events[0].data["webhook_id"] == webhook_id
    assert ifttt_events[0].data["hello"] == "ifttt"

    # Invalid JSON
    await client.post(f"/api/webhook/{webhook_id}", data="not a dict")
    assert len(ifttt_events) == 1

    # Not a dict
    await client.post(f"/api/webhook/{webhook_id}", json="not a dict")
    assert len(ifttt_events) == 1
