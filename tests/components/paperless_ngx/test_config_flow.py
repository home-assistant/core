"""Tests for the AdGuard Home config flow."""

import aiohttp

from homeassistant import config_entries
from homeassistant.components.paperless_ngx.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import USER_INPUT

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on AdGuard Home connection error."""

    aioclient_mock.get(
        (f"https://{USER_INPUT[CONF_HOST]}/api/schema/"),
        exc=aiohttp.ClientError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_invalid_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on AdGuard Home connection error."""

    aioclient_mock.get(
        (f"https://{USER_INPUT[CONF_HOST]}/api/"),
        exc=aiohttp.ClientResponseError(
            request_info=None,
            history=(),
            status=401,
        ),
    )
    aioclient_mock.get(
        (f"https://{USER_INPUT[CONF_HOST]}/api/schema/"),
        exc=aiohttp.ClientResponseError(
            request_info=None,
            history=(),
            status=401,
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_auth"}


async def test_full_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test registering an integration and finishing flow works."""

    aioclient_mock.get(
        (f"https://{USER_INPUT[CONF_HOST]}/api/schema/"),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    aioclient_mock.get(
        f"https://{USER_INPUT[CONF_HOST]}/api/tags/?page=1&page_size=150",
        headers={"Content-Type": CONTENT_TYPE_JSON},
        json={
            "count": 0,
            "next": None,
            "previous": None,
            "all": [],
            "results": [],
        },
    )

    assert result
    assert result["flow_id"]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    config_entry = result["result"]
    assert config_entry.title == "Paperless-ngx"
    assert config_entry.data == USER_INPUT


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=USER_INPUT,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
