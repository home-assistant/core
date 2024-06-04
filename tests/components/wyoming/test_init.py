"""Test init."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_cannot_connect(
    hass: HomeAssistant, stt_config_entry: ConfigEntry
) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=None,
    ):
        assert not await hass.config_entries.async_setup(stt_config_entry.entry_id)


async def test_unload(
    hass: HomeAssistant, stt_config_entry: ConfigEntry, init_wyoming_stt
) -> None:
    """Test unload."""
    assert await hass.config_entries.async_unload(stt_config_entry.entry_id)
