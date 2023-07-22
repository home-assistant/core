"""Test the No-IP.com config flow."""
from __future__ import annotations

import asyncio

import aiohttp
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import no_ip
from homeassistant.const import (
    CONF_DOMAIN,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
        params={"hostname": "test.ipv64.de.test"},
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
            "domain": "test.ipv64.de.test",
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
        params={"hostname": "test.ipv64.de.test"},
        status=200,
        text="good 1.2.3.4",
        exc=asyncio.TimeoutError,
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.ipv64.de.test",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_exception(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test capturing a connection exception in async_validate_no_ip."""
    aioclient_mock.get(
        no_ip.const.UPDATE_URL,
        params={"hostname": "test.ipv64.de.test"},
        exc=aiohttp.ClientError,
        status=200,
        text="good 1.2.3.4",
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.ipv64.de.test",
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
        params={"hostname": "test.ipv64.de.test"},
        status=200,
        text="unknown",
        exc=HomeAssistantError,
    )
    result = await hass.config_entries.flow.async_init(
        no_ip.const.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.2.3.4",
            CONF_DOMAIN: "test.ipv64.de.test",
            CONF_USERNAME: "abc@123.com",
            CONF_PASSWORD: "xyz789",
        },
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}
