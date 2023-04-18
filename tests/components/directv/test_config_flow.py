"""Test the DirecTV config flow."""
import dataclasses
from unittest.mock import patch

from aiohttp import ClientError as HTTPClientError

from homeassistant.components.directv.const import CONF_RECEIVER_ID, DOMAIN
from homeassistant.components.ssdp import ATTR_UPNP_SERIAL
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    HOST,
    MOCK_SSDP_DISCOVERY_INFO,
    MOCK_USER_INPUT,
    RECEIVER_ID,
    UPNP_SERIAL,
    mock_connection,
    setup_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM


async def test_show_ssdp_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the ssdp confirmation form is served."""
    mock_connection(aioclient_mock)

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: HOST}


async def test_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on connection error."""
    aioclient_mock.get("http://127.0.0.1:8080/info/getVersion", exc=HTTPClientError)

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_ssdp_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow on connection error."""
    aioclient_mock.get("http://127.0.0.1:8080/info/getVersion", exc=HTTPClientError)

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_confirm_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow on connection error."""
    aioclient_mock.get("http://127.0.0.1:8080/info/getVersion", exc=HTTPClientError)

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP, CONF_HOST: HOST, CONF_NAME: HOST},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort user flow if DirecTV receiver already configured."""
    await setup_integration(hass, aioclient_mock, skip_entry_setup=True)

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow if DirecTV receiver already configured."""
    await setup_integration(hass, aioclient_mock, skip_entry_setup=True)

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_with_receiver_id_device_exists_abort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow if DirecTV receiver already configured."""
    await setup_integration(hass, aioclient_mock, skip_entry_setup=True)

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    discovery_info.upnp[ATTR_UPNP_SERIAL] = UPNP_SERIAL
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on unknown error."""
    user_input = MOCK_USER_INPUT.copy()
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow on unknown error."""
    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_SSDP},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_confirm_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow on unknown error."""
    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    with patch(
        "homeassistant.components.directv.config_flow.DIRECTV.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_SSDP, CONF_HOST: HOST, CONF_NAME: HOST},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = MOCK_USER_INPUT.copy()
    with patch("homeassistant.components.directv.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_RECEIVER_ID] == RECEIVER_ID


async def test_full_ssdp_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full SSDP flow from start to finish."""
    mock_connection(aioclient_mock)

    discovery_info = dataclasses.replace(MOCK_SSDP_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"
    assert result["description_placeholders"] == {CONF_NAME: HOST}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_RECEIVER_ID] == RECEIVER_ID
