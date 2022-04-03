"""Test the CO2Signal diagnostics."""
from unittest.mock import patch

from homeassistant.components.co2signal import DOMAIN
from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_API_KEY
from homeassistant.setup import async_setup_component

from . import VALID_PAYLOAD

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client):
    """Test config entry diagnostics."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "api_key", "location": ""}
    )
    config_entry.add_to_hass(hass)
    with patch("CO2Signal.get_latest", return_value=VALID_PAYLOAD):
        assert await async_setup_component(hass, DOMAIN, {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    config_entry_dict = config_entry.as_dict()
    config_entry_dict["data"][CONF_API_KEY] = REDACTED

    assert result == {
        "config_entry": config_entry_dict,
        "data": VALID_PAYLOAD,
    }
