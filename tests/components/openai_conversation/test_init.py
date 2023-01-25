"""Tests for the OpenAI integration."""
from unittest.mock import patch

from homeassistant.components import conversation
from homeassistant.core import Context
from homeassistant.helpers import device_registry


async def test_default_prompt(hass, mock_init_component):
    """Test that the default prompt works."""
    device_reg = device_registry.async_get(hass)

    device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "1234")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
        suggested_area="Test Area",
    )
    device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "5678")},
        name="Test Device 2",
        manufacturer="Test Manufacturer 2",
        model="Test Model 2",
        suggested_area="Test Area 2",
    )
    device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3",
        suggested_area="Test Area 2",
    )

    with patch("openai.Completion.create") as mock_create:
        await conversation.async_converse(hass, "hello", None, Context())

    assert (
        mock_create.mock_calls[0][2]["prompt"]
        == """You are a conversational AI for a smart home named test home.
If a user wants to control a device, reject the request and suggest using the Home Assistant UI.

An overview of the areas and the devices in this smart home:

Test Area:

- Test Device (Test Model by Test Manufacturer)

Test Area 2:

- Test Device 2 (Test Model 2 by Test Manufacturer 2)
- Test Device 3 (Test Model 3 by Test Manufacturer 3)


Now finish this conversation:

Smart home: How can I assist?
User: hello
Smart home: """
    )
