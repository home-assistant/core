"""Test the Cloudflare switch platform."""

from unittest.mock import MagicMock

from homeassistant.components.cloudflare.const import DOMAIN
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import init_integration

import pytest


@pytest.mark.usefixtures("location_info")
async def test_switch_setup(
    hass: HomeAssistant, cfupdate: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Test the Cloudflare switch setup and state."""
    entry = await init_integration(hass)
    
    # Check if switch is created for the domain
    # Find entity_id by unique_id
    unique_id = "mock-zone-id_ha.mock.com_proxied"
    entry = entity_registry.async_get_entity_id("switch", DOMAIN, unique_id)
    assert entry
    
    state = hass.states.get(entry)
    assert state
    assert state.state == STATE_ON  # Initially proxied=True in mock data


@pytest.mark.usefixtures("location_info")
async def test_switch_turn_off(
    hass: HomeAssistant, cfupdate: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Test turning off the proxy switch."""
    client = cfupdate.return_value
    
    await init_integration(hass)
    
    unique_id = "mock-zone-id_ha.mock.com_proxied"
    entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, unique_id)
    assert entity_id
    
    # Turn off
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )
    
    # Verify client call
    # The client method is update_dns_record
    assert client.update_dns_record.called
    # Check arguments: record_proxied=False
    _args, kwargs = client.update_dns_record.call_args
    # In __init__.py it could be args or kwargs depending on call.
    # client.update_dns_record(..., record_proxied=False)
    assert kwargs.get("record_proxied") is False


@pytest.mark.usefixtures("location_info")
async def test_switch_turn_on(
    hass: HomeAssistant, cfupdate: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Test turning on the proxy switch."""
    client = cfupdate.return_value
    # Modify the mock records to have proxied=False for ha.mock.com
    records = client.list_dns_records.return_value
    # records is a list of dicts.
    # Find ha.mock.com
    for r in records:
        if r["name"] == "ha.mock.com":
            r["proxied"] = False
            break
            
    await init_integration(hass)
    
    unique_id = "mock-zone-id_ha.mock.com_proxied"
    entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, unique_id)
    assert entity_id

    # Turn on
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )
    
    assert client.update_dns_record.called
    _args, kwargs = client.update_dns_record.call_args
    assert kwargs.get("record_proxied") is True
