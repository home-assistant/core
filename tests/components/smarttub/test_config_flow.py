"""Test the smarttub config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.smarttub.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.smarttub.config_flow.validate_credentials",
        autospec=True,
        return_value=True,
    ), patch(
        "homeassistant.components.smarttub.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.smarttub.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "test-email", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-email"
    assert result2["data"] == {
        "email": "test-email",
        "password": "test-password",
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
        "homeassistant.components.smarttub.config_flow.validate_credentials",
        autospec=True,
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "test-email", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
