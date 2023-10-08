"""Test the Aussie Broadband config flow."""
from http import HTTPStatus

from aiohttp import ClientConnectionError

from homeassistant import config_entries
from homeassistant.components.splunk import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONFIG, RETURN_BADAUTH, RETURN_SUCCESS, URL, setup_platform

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test we get the form."""

    aioclient_mock.post(
        URL,
        text=RETURN_SUCCESS,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        CONFIG,
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONFIG[CONF_HOST]
    assert result2["data"] == CONFIG


async def test_form_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test invalid auth is handled."""

    aioclient_mock.post(
        URL,
        text=RETURN_BADAUTH,
        status=HTTPStatus.FORBIDDEN,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        CONFIG,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_network_issue(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test network issues are handled."""
    aioclient_mock.post(
        URL,
        side_effect=ClientConnectionError,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        CONFIG,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test successful reauth flow."""

    # Test success
    aioclient_mock.post(
        URL,
        text=RETURN_SUCCESS,
    )
    entry = await setup_platform(hass)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        {
            CONF_TOKEN: CONFIG[CONF_TOKEN],
        },
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test failed reauth flow."""

    # Test success
    aioclient_mock.post(
        URL,
        text=RETURN_BADAUTH,
        status=HTTPStatus.FORBIDDEN,
    )
    entry = await setup_platform(hass)

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )
    assert result1["type"] == FlowResultType.FORM
    assert result1["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        {
            CONF_TOKEN: "bad?",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
