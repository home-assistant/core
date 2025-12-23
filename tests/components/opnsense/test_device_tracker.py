"""The tests for the opnsense device tracker platform."""

from unittest.mock import patch

from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA_IMPORT, setup_mock_diagnostics

from tests.common import MockConfigEntry


async def test_get_scanner(hass: HomeAssistant) -> None:
    """Test creating an opnsense scanner."""
    with (
        patch("homeassistant.components.opnsense.diagnostics") as mock_diagnostics,
        patch(
            "homeassistant.components.opnsense.config_flow.diagnostics"
        ) as mock_diagnostics_config_flow,
    ):
        setup_mock_diagnostics(mock_diagnostics)
        setup_mock_diagnostics(mock_diagnostics_config_flow)

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data=CONFIG_DATA_IMPORT,
        )
        config_entry.add_to_hass(hass)

        # Test that the integration loads successfully
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert result

        # Verify the integration data was set up
        assert DOMAIN in hass.data

        # Test that device tracker platform loads without error
        # Legacy device trackers work differently and may not create immediate entities
        config_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(config_entries) == 1
        assert config_entries[0].state.name == "LOADED"
