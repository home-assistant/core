"""Test the No-IP.com config flow."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import no_ip
from homeassistant.components.no_ip.config_flow import async_validate_no_ip
from homeassistant.components.no_ip.const import DOMAIN
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    ("response_text", "result_type", "result_type2"),
    [
        (
            "good 192.168.1.1",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.CREATE_ENTRY,
        ),
        (
            "nochg 192.168.1.1",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.CREATE_ENTRY,
        ),
        (
            "nohost",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.FORM,
        ),
        (
            "badauth",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.FORM,
        ),
        (
            "badagent",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.FORM,
        ),
        (
            "!donator",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.FORM,
        ),
        (
            "abuse",
            data_entry_flow.FlowResultType.FORM,
            data_entry_flow.FlowResultType.FORM,
        ),
    ],
)
async def test_form_user(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response_text: str,
    result_type: data_entry_flow.FlowResultType,
    result_type2: data_entry_flow.FlowResultType,
) -> None:
    """Test the user step of the No-IP.com config flow."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=200,
        text=response_text,
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == result_type
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            "domain": "test.example.com",
            "username": "test_user",
            "password": "test_password",
        },
    )
    assert result["type"] == result_type2
    assert not hasattr(result, "exception")


async def test_timeout_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test capturing a timeout error in async_validate_no_ip."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=200,
        text="good 1.2.3.4",
        exc=asyncio.TimeoutError,
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_connection_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test capturing a connection exception in async_validate_no_ip."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        exc=aiohttp.ClientError,
        status=200,
        text="good 1.2.3.4",
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test capturing an "unknown" exception in async_validate_no_ip."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=200,
        text="unknown",
        exc=HomeAssistantError,
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_cannot_connect_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test capturing a cannot_connect error in async_validate_no_ip."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=200,
        exc=aiohttp.ClientError,
    )
    with pytest.raises(aiohttp.ClientError):
        await async_validate_no_ip(
            hass,
            {
                CONF_IP_ADDRESS: "1.2.3.4",
                CONF_DOMAIN: "test.example.com",
                CONF_USERNAME: "abc@123.com",
                CONF_PASSWORD: "xyz789",
            },
        )


async def test_unexpected_status_code(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test handling of unexpected status code from No-IP.com."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=500,  # Use a status code that is not 200 or 401
        text="server error",
    )
    result = await async_validate_no_ip(
        hass,
        {
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.example.com",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
    )
    assert result == {"title": no_ip.const.MANUFACTURER, "exception": "unknown"}


async def test_async_step_import(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test async_step_import."""
    # Test case: Import data is None, expect transition to async_step_user
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Test case: Import data with matching domain and username, expect async_abort
    existing_entry = MockConfigEntry(
        domain=DOMAIN, data={"domain": "test.example.com", "username": "abc@123.com"}
    )
    existing_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"domain": "test.example.com", "username": "abc@123.com"},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    # Test case: Import data with no exception, expect transition to async_step_user
    import_data = {}
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=200,
        text="good 1.2.3.4",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=import_data
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Test case: Import data with exception, expect async_abort
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.example.com"},
        status=200,
        text="badauth",
    )
    import_data = {
        "domain": "test.example.com",
        "username": "testuser",
        "password": "testpassword",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=import_data
    )
    assert result["type"] == "create_entry"
    assert result["data"] == import_data
    assert result["context"] == {"source": config_entries.SOURCE_IMPORT}
