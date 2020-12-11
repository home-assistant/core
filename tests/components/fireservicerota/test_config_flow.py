"""Test the FireServiceRota config flow."""
from pyfireservicerota import InvalidAuthError

from homeassistant import data_entry_flow
from homeassistant.components.fireservicerota.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

MOCK_CONF = {
    CONF_USERNAME: "my@email.address",
    CONF_PASSWORD: "mypassw0rd",
    CONF_URL: "www.brandweerrooster.nl",
}

MOCK_DATA = {
    "auth_implementation": DOMAIN,
    CONF_URL: MOCK_CONF[CONF_URL],
    CONF_USERNAME: MOCK_CONF[CONF_USERNAME],
    "token": {
        "access_token": "test-access-token",
        "token_type": "Bearer",
        "expires_in": 1234,
        "refresh_token": "test-refresh-token",
        "created_at": 4321,
    },
}

MOCK_TOKEN_INFO = {
    "access_token": "test-access-token",
    "token_type": "Bearer",
    "expires_in": 1234,
    "refresh_token": "test-refresh-token",
    "created_at": 4321,
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
        assert result["errors"] == {"base": "invalid_auth"}


async def test_step_user(hass):
    """Test the start of the config flow."""

    with patch(
        "homeassistant.components.fireservicerota.config_flow.FireServiceRota"
    ) as mock_fsr, patch(
        "homeassistant.components.fireservicerota.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.fireservicerota.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:

        mock_fireservicerota = mock_fsr.return_value
        mock_fireservicerota.request_tokens.return_value = MOCK_TOKEN_INFO

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=MOCK_CONF
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == MOCK_CONF[CONF_USERNAME]
        assert result["data"] == {
            "auth_implementation": "fireservicerota",
            CONF_URL: "www.brandweerrooster.nl",
            CONF_USERNAME: "my@email.address",
            "token": {
                "access_token": "test-access-token",
                "token_type": "Bearer",
                "expires_in": 1234,
                "refresh_token": "test-refresh-token",
                "created_at": 4321,
            },
        }

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
