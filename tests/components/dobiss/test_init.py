"""Test setup and unload behavior for Dobiss integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_and_unload_entry(hass: HomeAssistant, config_entry) -> None:
    """Test setup and unload of entry."""

    # Voeg de mock config_entry toe aan Home Assistant
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dobiss.DobissAPI.discovery", new=AsyncMock()),
        patch(
            "homeassistant.components.dobiss.DobissAPI.listen_for_dobiss",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.dobiss.DobissAPI.auth_check",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_component(hass, "dobiss", {})
        await hass.async_block_till_done()

    assert "dobiss" in hass.data

    # Simuleer unload
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert "dobiss" not in hass.data
