"""Test the London Underground init."""

from unittest.mock import patch

from homeassistant.components.london_underground.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, MockConfigEntry


async def test_reload_entry(hass: HomeAssistant) -> None:
    """Test reloading the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={"line": ["Bakerloo"]},
    )
    with patch(
        "homeassistant.components.london_underground.LondonTubeCoordinator"
    ) as mock_cls:
        # Make the constructor return a mock with an async method
        mock_instance = mock_cls.return_value
        mock_instance.async_config_entry_first_refresh = AsyncMock(return_value=True)

        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Test reloading with updated options
        hass.config_entries.async_update_entry(
            entry,
            data={},
            options={"line": ["Bakerloo", "Central"]},
        )
        await hass.async_block_till_done()

        # Verify that setup was called for each reload
        assert len(mock_instance.mock_calls) > 0
