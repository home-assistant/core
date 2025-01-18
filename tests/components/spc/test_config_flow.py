"""Test the SPC config flow."""

from unittest.mock import patch

from aiohttp import ClientError

from homeassistant import config_entries
from homeassistant.components.spc import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.spc.config_flow.SpcWebGateway.async_load_parameters",
            return_value=True,
        ),
        patch(
            "homeassistant.components.spc.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_url": "http://example.com/api",
                "ws_url": "ws://example.com/ws",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "SPC"
    assert result2["data"] == {
        "api_url": "http://example.com/api",
        "ws_url": "ws://example.com/ws",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.spc.config_flow.SpcWebGateway.async_load_parameters",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_url": "http://example.com/api",
                "ws_url": "ws://example.com/ws",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.spc.config_flow.SpcWebGateway.async_load_parameters",
        side_effect=ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_url": "http://example.com/api",
                "ws_url": "ws://example.com/ws",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
