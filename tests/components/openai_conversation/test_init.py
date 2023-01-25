"""Tests for the OpenAI integration."""

from homeassistant.components.openai_conversation import OpenAIAgent
from homeassistant.helpers import device_registry


async def test_default_prompt(hass):
    """Test that the default prompt works."""
    agent = OpenAIAgent(hass, None)

    hass.states.async_set(
        "person.test_person", "home", {"friendly_name": "Test Person"}
    )

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

    assert (
        agent._async_generate_prompt()
        == """
You are a smart home named test home.
Reject any request to control a device and tell user to use the Home Assistant UI.

The people living in the home are:
- Test Person. They are currently home

An overview of the areas and the devices in the home:


Test Area:

- Test Device (Test Model by Test Manufacturer)

Test Area 2:

- Test Device 2 (Test Model 2 by Test Manufacturer 2)
- Test Device 3 (Test Model 3 by Test Manufacturer 3)


Now finish this conversation:

Smart home: How can I assist?
""".strip()
    )
