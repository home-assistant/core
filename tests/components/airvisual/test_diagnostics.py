"""Test evil genius labs diagnostics."""
from unittest.mock import patch

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass, config_entry, data, hass_client, setup_airvisual
):
    """Test config entry diagnostics."""
    with patch("pyairvisual.air_quality.AirQuality.nearest_city", return_value=data):
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
            == {}
        )
