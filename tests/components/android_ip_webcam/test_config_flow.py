"""Test the Android IP Webcam config flow."""

from http import HTTPStatus
from unittest.mock import Mock, patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.android_ip_webcam.const import DOMAIN
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .test_init import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_form(hass: HomeAssistant, aioclient_mock_fixture) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.android_ip_webcam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 8080,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 8080,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_device_already_configured(
    hass: HomeAssistant, aioclient_mock_fixture
) -> None:
    """Test aborting if the device is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
            "port": 8080,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        exc=aiohttp.ClientResponseError(Mock(), (), status=401),
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "port": 8080, "username": "user", "password": "wrong-pass"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"username": "invalid_auth", "password": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        text=await async_load_fixture(hass, "android_ip_webcam/status_data.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://1.1.1.1:8080/sensors.json",
        text=await async_load_fixture(hass, "android_ip_webcam/sensor_data.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    with patch(
        "homeassistant.components.android_ip_webcam.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "port": 8080, "username": "user", "password": "pass"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY


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

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        text=await async_load_fixture(hass, "android_ip_webcam/status_data.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://1.1.1.1:8080/sensors.json",
        text=await async_load_fixture(hass, "android_ip_webcam/sensor_data.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    with patch(
        "homeassistant.components.android_ip_webcam.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
