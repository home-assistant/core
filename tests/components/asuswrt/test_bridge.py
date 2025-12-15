"""Unit tests for bridge."""

from homeassistant.components.asuswrt.bridge import AsusWrtLegacyBridge

from .common import CONFIG_DATA_TELNET


async def test_get_rates_none_value(connect_legacy) -> None:
    """Test AsusWrtLegacyBridge._get_rates with None value."""
    connect_legacy.return_value.get_current_transfer_rates.return_value = None
    assert await AsusWrtLegacyBridge(CONFIG_DATA_TELNET)._get_rates() is None
