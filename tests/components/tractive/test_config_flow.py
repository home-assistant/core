"""Test the tractive config flow."""
from unittest.mock import patch

import aiotractive

from homeassistant import config_entries, setup
from homeassistant.components.tractive.const import DOMAIN
from homeassistant.core import HomeAssistant

USER_INPUT = {
    "email": "test-email@example.com",
    "password": "test-password",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "aiotractive.api.API.user_id", return_value={"user_id": "user_id"}
    ), patch(
        "homeassistant.components.tractive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-email@example.com"
    assert result2["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiotractive.api.API.user_id",
        side_effect=aiotractive.exceptions.UnauthorizedError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiotractive.api.API.user_id",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
