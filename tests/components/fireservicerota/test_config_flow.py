"""Test the FireServiceRota config flow."""
from pyfireservicerota import InvalidAuthError

from homeassistant import data_entry_flow
from homeassistant.components.fireservicerota.const import (  # pylint: disable=unused-import
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_CONF = {
    CONF_USERNAME: "my@email.address",
    CONF_PASSWORD: "mypassw0rd",
    CONF_URL: "brandweerrooster.nl",
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_abort_if_already_setup(hass):
    """Test abort if already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONF, unique_id=MOCK_CONF[CONF_USERNAME]
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_CONF
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""

    with patch(
        "homeassistant.components.fireservicerota.FireServiceRota.request_tokens",
        side_effect=InvalidAuthError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_CONF
        )
        assert result["errors"] == {"base": "invalid_credentials"}
