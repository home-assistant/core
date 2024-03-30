"""Test the APsystems Local API config flow."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant import config_entries
from homeassistant.components.apsystemsapi_local.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_NAME: "Solar",
            "check": False,
            "update_interval": 15,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solar"
    assert result["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_NAME: "Solar",
        "check": False,
        "update_interval": 15,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    aioclient_mock.get(
        "http://127.0.0.1:8050/getDeviceInfo", exc=aiohttp.ClientConnectionError
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_NAME: "Solar",
            "check": True,
            "update_interval": 15,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "connection_refused"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_NAME: "Solar",
            "check": False,
            "update_interval": 15,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Solar"
    assert result["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_NAME: "Solar",
        "check": False,
        "update_interval": 15,
    }


async def test_form_with_connect_check(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    aioclient_mock.get(
        "http://127.0.0.1:8050/getDeviceInfo",
        json={
            "data": {
                "deviceId": "SOME_ID",
                "devVer": "EZ1 1.6.0",
                "ssid": "SOME_WIFI",
                "ipAddr": "SOME_IP",
                "minPower": "30",
                "maxPower": "800",
            },
            "message": "SUCCESS",
            "deviceId": "SOME_ID",
        },
        headers={"Content-Type": "application/json"},
    )

    try:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_NAME: "Solar",
                "check": True,
                "update_interval": 10,
            },
        )
        # AiohttpClientMockResponse does not have .ok
        # So, I check if it's coming that far and fail if that's not the case
        assert "OTHER_ERROR" == "CHECK_COMMENT"
    except AttributeError:
        pass
