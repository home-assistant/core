"""Tests for the OpenAI integration."""
from unittest.mock import patch

from openai import error

from homeassistant.components import conversation
from homeassistant.core import Context
from homeassistant.helpers import area_registry, device_registry, intent


async def test_default_prompt(hass, mock_init_component):
    """Test that the default prompt works."""
    device_reg = device_registry.async_get(hass)
    area_reg = area_registry.async_get(hass)

    for i in range(3):
        area_reg.async_create(f"{i}Empty Area")

    device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "1234")},
        name="Test Device",
        manufacturer="Test Manufacturer",
        model="Test Model",
        suggested_area="Test Area",
    )
    for i in range(3):
        device_reg.async_get_or_create(
            config_entry_id="1234",
            connections={("test", f"{i}abcd")},
            name="Test Service",
            manufacturer="Test Manufacturer",
            model="Test Model",
            suggested_area="Test Area",
            entry_type=device_registry.DeviceEntryType.SERVICE,
        )
    device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "5678")},
        name="Test Device 2",
        manufacturer="Test Manufacturer 2",
        model="Device 2",
        suggested_area="Test Area 2",
    )
    device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device = device_reg.async_get_or_create(
        config_entry_id="1234",
        connections={("test", "9876-disabled")},
        name="Test Device 3",
        manufacturer="Test Manufacturer 3",
        model="Test Model 3A",
        suggested_area="Test Area 2",
    )
    device_reg.async_update_device(
        device.id, disabled_by=device_registry.DeviceEntryDisabler.USER
    )

    with patch("openai.Completion.create") as mock_create:
        await conversation.async_converse(hass, "hello", None, Context())

    assert (
        mock_create.mock_calls[0][2]["prompt"]
        == """This smart home is controlled by Home Assistant.

An overview of the areas and the devices in this smart home:

Test Area:
- Test Device (Test Model)

Test Area 2:
- Test Device 2
- Test Device 3 (Test Model 3A)

Answer the users questions about the world truthfully.

If the user wants to control a device, reject the request and suggest using the Home Assistant UI.

Now finish this conversation:

Smart home: How can I assist?
User: hello
Smart home: """
    )


async def test_error_handling(hass, mock_init_component):
    """Test that the default prompt works."""
    with patch("openai.Completion.create", side_effect=error.ServiceUnavailableError):
        result = await conversation.async_converse(hass, "hello", None, Context())

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result
