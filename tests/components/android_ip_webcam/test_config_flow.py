"""Test the Android IP Webcam config flow."""
from unittest.mock import patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.android_ip_webcam.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_form(hass: HomeAssistant, aioclient_mock_fixture) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.android_ip_webcam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "IP Webcam"
    assert result2["data"] == {
        "name": "IP Webcam",
        "host": "1.1.1.1",
        "port": 8080,
        "timeout": 10,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant, aioclient_mock_fixture) -> None:
    """Test a successful import of yaml."""
    with patch(
        "homeassistant.components.android_ip_webcam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"name": "IP Webcam", "host": "1.1.1.1", "port": 8080, "timeout": 10},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "IP Webcam"
    assert result2["data"] == {
        "name": "IP Webcam",
        "host": "1.1.1.1",
        "port": 8080,
        "timeout": 10,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        exc=aiohttp.ClientError,
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
