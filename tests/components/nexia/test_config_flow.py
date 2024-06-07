"""Test the nexia config flow."""

from unittest.mock import MagicMock, patch

import aiohttp
from nexia.const import BRAND_ASAIR, BRAND_NEXIA
import pytest

from homeassistant import config_entries
from homeassistant.components.nexia.const import CONF_BRAND, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize("brand", [BRAND_ASAIR, BRAND_NEXIA])
async def test_form(hass: HomeAssistant, brand) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value="myhouse",
        ),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.login",
            side_effect=MagicMock(),
        ),
        patch(
            "homeassistant.components.nexia.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BRAND: brand, CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "myhouse"
    assert result2["data"] == {
        CONF_BRAND: brand,
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.login",
        ),
        patch(
            "homeassistant.components.nexia.config_flow.NexiaHome.get_name",
            return_value=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth_http_401(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error from http 401."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=aiohttp.ClientResponseError(
            status=401, request_info=MagicMock(), history=MagicMock()
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect_not_found(hass: HomeAssistant) -> None:
    """Test we handle cannot connect from an http not found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=aiohttp.ClientResponseError(
            status=404, request_info=MagicMock(), history=MagicMock()
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_broad_exception(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nexia.config_flow.NexiaHome.login",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BRAND: BRAND_NEXIA,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
