"""Tests for the Location component."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from homeassistant.generated import locations as loc_gen


async def test_setup(hass: HomeAssistant) -> None:
    """Test setup."""

    mock_loc = {
        "NL": [
            "buienradar",
        ],
    }
    with (
        patch.dict(
            loc_gen.LOCATIONS,
            mock_loc,
            clear=True,
        ),
        patch.object(hass.config_entries.flow, "async_init") as mock_config_flow,
    ):
