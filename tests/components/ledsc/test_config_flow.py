"""Test the LedSc config flow."""

from unittest.mock import patch, AsyncMock

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.components.ledsc.consts import DOMAIN
from websc_client.exceptions import WebSClientConnectionError

USER_INPUT = {"host": "127.0.0.1", "port": 8080}
IMPORT_CONFIG = {"host": "127.0.0.1", "port": 8080}
RESULT = {
    "type": "create_entry",
    "title": f"LedSC server {USER_INPUT['host']}:{USER_INPUT['port']}",
    "data": USER_INPUT,
}
ENTRY_CONFIG = {"host": "127.0.0.1", "port": 8080}


async def test_form(hass) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
            "homeassistant.components.ledsc.config_flow.validate_input",
            return_value=RESULT,
    ), patch(
        "homeassistant.components.ledsc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == RESULT["title"]
    assert result["data"] == USER_INPUT


async def test_form_cannot_connect(hass) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unique_id_check(hass):
    """Try to create 2 intance integration with the same configuration"""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=USER_INPUT,
    )

    magic_websc = AsyncMock()

    with patch(
            "homeassistant.components.ledsc.config_flow.WebSClient",
            autospe=True, return_value=magic_websc,
    ) as mock_websc:
        mock_websc.connect.side_effect = WebSClientConnectionError
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
