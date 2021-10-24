"""Tests for the TED config flow."""
from unittest.mock import patch

import httpx

from homeassistant import config_entries
from homeassistant.components.ted import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

CONFIG = {CONF_HOST: "127.0.0.1"}
CONFIG_FINAL = {CONF_HOST: "127.0.0.1", CONF_NAME: "TED ted5000"}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("tedpy.TED5000.check", return_value=True), patch(
        "tedpy.TED5000.update", return_value=True
    ), patch(
        "homeassistant.components.ted.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == CONFIG_FINAL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("tedpy.createTED", side_effect=httpx.HTTPError("any")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant) -> None:
    """Test we can import from yaml."""
    with patch("tedpy.TED5000.check", return_value=True), patch(
        "tedpy.TED5000.update", return_value=True
    ), patch(
        "homeassistant.components.ted.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "ip_address": "1.1.1.1",
                "name": "TED monitor",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "TED monitor"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "TED ted5000",
    }
    assert len(mock_setup_entry.mock_calls) == 1
