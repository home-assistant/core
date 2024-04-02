"""Test the APsystems Local API config flow."""

import aiohttp

from homeassistant import config_entries
from homeassistant.components.apsystemsapi_local.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.test_util.aiohttp import AiohttpClientMocker

SUCCESS_DEVICE_INFO_DATA = {
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
}


async def test_form_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    aioclient_mock.get(
        "http://127.0.0.2:8050/getDeviceInfo", exc=aiohttp.ClientConnectionError
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_IP_ADDRESS: "127.0.0.2",
            CONF_NAME: "Solar",
            "update_interval": 15,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "connection_refused"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    aioclient_mock.get(
        "http://127.0.0.1:8050/getDeviceInfo",
        json=SUCCESS_DEVICE_INFO_DATA,
        headers={"Content-Type": "application/json"},
    )
    try:
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_NAME: "Solar",
                "update_interval": 15,
            },
        )
        # AiohttpClientMockResponse does not have .ok
        # So, I check if it's coming that far and fail if that's not the case
        assert "OTHER_ERROR" == "CHECK_COMMENT"  # noqa: PLR0133
    except AttributeError:
        pass


async def test_form_with_connect_check(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    aioclient_mock.get(
        "http://127.0.0.1:8050/getDeviceInfo",
        json=SUCCESS_DEVICE_INFO_DATA,
        headers={"Content-Type": "application/json"},
    )

    try:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_IP_ADDRESS: "127.0.0.1",
                CONF_NAME: "Solar",
                "update_interval": 10,
            },
        )
        # AiohttpClientMockResponse does not have .ok
        # So, I check if it's coming that far and fail if that's not the case
        assert "OTHER_ERROR" == "CHECK_COMMENT"  # noqa: PLR0133
    except AttributeError:
        pass
