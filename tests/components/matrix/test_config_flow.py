"""Test the Matrix config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.matrix.config_flow import InvalidAuth
from homeassistant.components.matrix.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("matrix_client.client.MatrixClient.login", return_value=True,), patch(
        "homeassistant.components.matrix.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.matrix.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "homeserver": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "MatrixServer"
    assert result2["data"] == {
        "homeserver": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "verify_ssl": True,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "matrix_client.client.MatrixClient.login", side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "homeserver": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
