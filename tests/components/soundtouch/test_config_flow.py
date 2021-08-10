"""Test config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.soundtouch.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SOURCE,
    CONTENT_TYPE_TEXT_PLAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_full_user_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the zeroconf flow from start to finish."""
    aioclient_mock.get(
        "http://127.0.0.1:8090/info",
        text=load_fixture("soundtouch/info.xml"),
        headers={"Content-Type": CONTENT_TYPE_TEXT_PLAIN},
    )
    # Start a discovered configuration flow, to guarantee a user flow doesn't abort
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "DeviceName",
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 8090,
        },
    )

    assert result["description_placeholders"] == {CONF_NAME: "DeviceName"}
    assert result["step_id"] == "confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "DeviceName"
    assert result["data"][CONF_NAME] == "DeviceName"
    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert result["data"][CONF_PORT] == 8090


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the zeroconf flow from start to finish."""
    aioclient_mock.get(
        "http://127.0.0.1:8090/info",
        text=load_fixture("soundtouch/info.xml"),
        headers={"Content-Type": CONTENT_TYPE_TEXT_PLAIN},
    )
    # Start a discovered configuration flow, to guarantee a user flow doesn't abort
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data={
            "host": "127.0.0.1",
            "port": 8090,
            "hostname": "Bose-SM2-1862e443e08d.local.",
            "type": "_soundtouch._tcp.local.",
            "name": "DeviceName._soundtouch._tcp.local.",
            "properties": {
                "DESCRIPTION": "SoundTouch",
                "MAC": "F4E11EDB7E6A",
                "MANUFACTURER": "Bose Corporation",
                "MODEL": "SoundTouch",
            },
        },
    )
    assert result["description_placeholders"] == {CONF_NAME: "DeviceName"}
    assert result["step_id"] == "confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "DeviceName"
    assert result["data"][CONF_NAME] == "DeviceName"
    assert result["data"][CONF_HOST] == "127.0.0.1"
    assert result["data"][CONF_PORT] == 8090
