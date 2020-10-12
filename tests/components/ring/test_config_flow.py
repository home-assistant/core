"""Test the Ring config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.ring import DOMAIN
from homeassistant.components.ring.config_flow import InvalidAuth

from tests.async_mock import Mock, patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.ring.config_flow.Auth",
        return_value=Mock(
            fetch_token=Mock(return_value={"access_token": "mock-token"})
        ),
    ), patch(
        "homeassistant.components.ring.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.ring.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "hello@home-assistant.io", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "hello@home-assistant.io"
    assert result2["data"] == {
        "username": "hello@home-assistant.io",
        "token": {"access_token": "mock-token"},
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
        "homeassistant.components.ring.config_flow.Auth.fetch_token",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "hello@home-assistant.io", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
