"""Test Alexa entity representation."""
from unittest.mock import patch

from homeassistant.components.alexa import smart_home
from homeassistant.const import __version__
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from .test_common import get_default_config, get_new_request


async def test_unsupported_domain(hass):
    """Discovery ignores entities of unknown domains."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("woz.boop", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)

    assert "event" in msg
    msg = msg["event"]

    assert not msg["payload"]["endpoints"]


async def test_categorized_hidden_entities(hass):
    """Discovery ignores hidden and categorized entities."""
    entity_registry = er.async_get(hass)
    request = get_new_request("Alexa.Discovery", "Discover")

    entity_entry1 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_config_id",
        suggested_object_id="config_switch",
        entity_category=EntityCategory.CONFIG,
    )
    entity_entry2 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_diagnostic_id",
        suggested_object_id="diagnostic_switch",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    entity_entry3 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_hidden_integration_id",
        suggested_object_id="hidden_integration_switch",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    entity_entry4 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_hidden_user_id",
        suggested_object_id="hidden_user_switch",
        hidden_by=er.RegistryEntryHider.USER,
    )

    # These should not show up in the sync request
    hass.states.async_set(entity_entry1.entity_id, "on")
    hass.states.async_set(entity_entry2.entity_id, "something_else")
    hass.states.async_set(entity_entry3.entity_id, "blah")
    hass.states.async_set(entity_entry4.entity_id, "foo")

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)

    assert "event" in msg
    msg = msg["event"]

    assert not msg["payload"]["endpoints"]


async def test_serialize_discovery(hass):
    """Test we handle an interface raising unexpectedly during serialize discovery."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("switch.bla", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)

    assert "event" in msg
    msg = msg["event"]
    endpoint = msg["payload"]["endpoints"][0]

    assert endpoint["additionalAttributes"] == {
        "manufacturer": "Home Assistant",
        "model": "switch",
        "softwareVersion": __version__,
        "customIdentifier": "mock-user-id-switch.bla",
    }


async def test_serialize_discovery_recovers(hass, caplog):
    """Test we handle an interface raising unexpectedly during serialize discovery."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("switch.bla", "on", {"friendly_name": "Boop Woz"})

    with patch(
        "homeassistant.components.alexa.capabilities.AlexaPowerController.serialize_discovery",
        side_effect=TypeError,
    ):
        msg = await smart_home.async_handle_message(
            hass, get_default_config(hass), request
        )

    assert "event" in msg
    msg = msg["event"]

    interfaces = {
        ifc["interface"] for ifc in msg["payload"]["endpoints"][0]["capabilities"]
    }

    assert "Alexa.PowerController" not in interfaces
    assert (
        f"Error serializing Alexa.PowerController discovery for {hass.states.get('switch.bla')}"
        in caplog.text
    )
