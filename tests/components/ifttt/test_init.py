"""Test the init file of IFTTT."""

from unittest.mock import patch

import pytest
import requests

from homeassistant import config_entries
from homeassistant.components import ifttt
from homeassistant.components.ifttt import CONF_KEY, DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from tests.common import async_setup_component
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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


async def test_trigger_service_raises_when_ifttt_unreachable(
    hass: HomeAssistant,
) -> None:
    """Test trigger_service raises when IFTTT cannot be reached."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_KEY: "secret"}})

    with (
        patch(
            "homeassistant.components.ifttt.pyfttt.send_event",
            side_effect=requests.exceptions.ConnectionError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            ifttt.SERVICE_TRIGGER,
            {"event": "test_event"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "trigger_failed"
