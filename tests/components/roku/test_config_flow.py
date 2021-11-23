"""Test the Roku config flow."""
import dataclasses
from unittest.mock import patch

from homeassistant.components.roku.const import DOMAIN
from homeassistant.config_entries import SOURCE_HOMEKIT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.components.roku import (
    HOMEKIT_HOST,
    HOST,
    MOCK_HOMEKIT_DISCOVERY_INFO,
    MOCK_SSDP_DISCOVERY_INFO,
    NAME_ROKUTV,
    UPNP_FRIENDLY_NAME,
    mock_connection,
    setup_integration,
)
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_duplicate_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that errors are shown when duplicates are added."""
    await setup_integration(hass, aioclient_mock, skip_entry_setup=True)
    mock_connection(aioclient_mock)

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=user_input
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    user_input = {CONF_HOST: HOST}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=user_input
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    discovery_info = MOCK_SSDP_DISCOVERY_INFO.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test the user step."""

    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == UPNP_FRIENDLY_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect roku error."""
    mock_connection(aioclient_mock, error=True)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"], user_input={CONF_HOST: HOST}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    user_input = {CONF_HOST: HOST}
    with patch(
        "homeassistant.components.roku.config_flow.Roku.update",
        side_effect=Exception,
    ) as mock_validate_input:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=user_input
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"

    await hass.async_block_till_done()
    assert len(mock_validate_input.mock_calls) == 1


async def test_homekit_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort homekit flow on connection error."""
    mock_connection(
        aioclient_mock,
        host=HOMEKIT_HOST,
        error=True,
    )

    discovery_info = dataclasses.replace(MOCK_HOMEKIT_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_HOMEKIT},
        data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_homekit_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort homekit flow on unknown error."""
    discovery_info = dataclasses.replace(MOCK_HOMEKIT_DISCOVERY_INFO)
    with patch(
        "homeassistant.components.roku.config_flow.Roku.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_HOMEKIT},
            data=discovery_info,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_homekit_discovery(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the homekit discovery flow."""
    mock_connection(aioclient_mock, device="rokutv", host=HOMEKIT_HOST)

    discovery_info = dataclasses.replace(MOCK_HOMEKIT_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_HOMEKIT}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {CONF_NAME: NAME_ROKUTV}

    with patch(
        "homeassistant.components.roku.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME_ROKUTV

    assert result["data"]
    assert result["data"][CONF_HOST] == HOMEKIT_HOST
    assert result["data"][CONF_NAME] == NAME_ROKUTV

    assert len(mock_setup_entry.mock_calls) == 1

    # test abort on existing host
    discovery_info = dataclasses.replace(MOCK_HOMEKIT_DISCOVERY_INFO)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_HOMEKIT}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow on connection error."""
    mock_connection(aioclient_mock, error=True)

    discovery_info = MOCK_SSDP_DISCOVERY_INFO.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_unknown_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we abort SSDP flow on unknown error."""
    discovery_info = MOCK_SSDP_DISCOVERY_INFO.copy()
    with patch(
        "homeassistant.components.roku.config_flow.Roku.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_SSDP},
            data=discovery_info,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_discovery(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the SSDP discovery flow."""
    mock_connection(aioclient_mock)

    discovery_info = MOCK_SSDP_DISCOVERY_INFO.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {CONF_NAME: UPNP_FRIENDLY_NAME}

    with patch(
        "homeassistant.components.roku.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == UPNP_FRIENDLY_NAME

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_NAME] == UPNP_FRIENDLY_NAME

    assert len(mock_setup_entry.mock_calls) == 1
