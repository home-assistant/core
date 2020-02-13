"""Test Dynalite config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.dynalite import CONF_HOST, DOMAIN


async def test_flow_works(hass):
    """Test config flow."""

    with patch(
        "homeassistant.components.dynalite.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_HOST: {}},
        )
    assert result["type"] == "create_entry"
