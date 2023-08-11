"""Test the JuiceNet config flow."""
from unittest.mock import MagicMock, patch

import aiohttp
from pyjuicenet import TokenError

from homeassistant import config_entries
from homeassistant.components.juicenet.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant


def _mock_juicenet_return_value(get_devices=None):
    juicenet_mock = MagicMock()
    type(juicenet_mock).get_devices = MagicMock(return_value=get_devices)
    return juicenet_mock


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.juicenet.config_flow.Api.get_devices",
        return_value=MagicMock(),
    ), patch(
        "homeassistant.components.juicenet.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.juicenet.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "access_token"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "JuiceNet"
    assert result2["data"] == {CONF_ACCESS_TOKEN: "access_token"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.juicenet.config_flow.Api.get_devices",
        side_effect=TokenError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "access_token"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.juicenet.config_flow.Api.get_devices",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "access_token"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_catch_unknown_errors(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.juicenet.config_flow.Api.get_devices",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "access_token"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_import(hass: HomeAssistant) -> None:
    """Test that import works as expected."""

    with patch(
        "homeassistant.components.juicenet.config_flow.Api.get_devices",
        return_value=MagicMock(),
    ), patch(
        "homeassistant.components.juicenet.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.juicenet.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_ACCESS_TOKEN: "access_token"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "JuiceNet"
    assert result["data"] == {CONF_ACCESS_TOKEN: "access_token"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
