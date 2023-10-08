"""Test LoRaWAN platform __init__ file."""
import pytest

from homeassistant import config_entries
from homeassistant.components.lorawan import async_setup_entry
from homeassistant.components.lorawan.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: config_entries.ConfigEntry,
    set_caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test LoRaWAN platform setup."""
    assert await async_setup_entry(hass, mock_config_entry) is True
    assert hass.data[DOMAIN] == {}

    assert set_caplog_debug.record_tuples == []
