"""Tests for Wibeee button platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


async def test_buttons_created(hass: HomeAssistant, loaded_entry) -> None:
    """Test that button entities are created."""
    states = hass.states.async_all("button")
    # Should have buttons for reboot and reset energy
    assert len(states) >= 2


async def test_reboot_button(hass: HomeAssistant, loaded_entry) -> None:
    """Test reboot button exists."""
    states = hass.states.async_all("button")
    button_names = [s.attributes.get("friendly_name") for s in states]
    assert any("Reboot" in name for name in button_names)


async def test_reset_energy_button(hass: HomeAssistant, loaded_entry) -> None:
    """Test reset energy button exists."""
    states = hass.states.async_all("button")
    button_names = [s.attributes.get("friendly_name") for s in states]
    assert any("Reset" in name for name in button_names)
