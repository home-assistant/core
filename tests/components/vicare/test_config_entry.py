"""Test the ViCare config flow."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_single_device(
    hass: HomeAssistant,
    mock_vicare_gas_boiler: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test default cache duration when using a single device."""
    assert mock_vicare_gas_boiler.cacheDuration == 60


async def test_config_entry_2_devices(
    hass: HomeAssistant,
    mock_vicare_2_gas_boilers: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test increased cache duration when using a multiple devices."""
    assert mock_vicare_2_gas_boilers.cacheDuration == 120
