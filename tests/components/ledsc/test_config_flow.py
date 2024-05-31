from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.ledsc.consts import DOMAIN

USER_INPUT = {"host": "127.0.0.1", "port": 8080}
IMPORT_CONFIG = {"host": "127.0.0.1", "port": 8080}
RESULT = {
    "type": "create_entry",
    "title": f"LedSC server {USER_INPUT['host']}:{USER_INPUT['port']}",
    "data": USER_INPUT,
}
ENTRY_CONFIG = {"host": "127.0.0.1", "port": 8080}


async def test_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
            "homeassistant.components.ledsc.config_flow.validate_input",
            return_value=RESULT,
    ), patch(
        "homeassistant.components.ledsc.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == RESULT["title"]
    assert result2["data"] == USER_INPUT


async def test_form_cannot_connect(hass):
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
            "homeassistant.components.ledsc.config_flow.validate_input",
            side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unique_id_check(hass):
    """Test we handle unique id check"""
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
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"