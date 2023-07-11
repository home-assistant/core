"""Test config flow."""
from unittest.mock import patch

from requests import RequestException
import requests_mock
from requests_mock import ANY, Mocker

from homeassistant.components.soundtouch.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_1_ID, DEVICE_1_IP, DEVICE_1_NAME


async def test_user_flow_create_entry(
    hass: HomeAssistant, device1_requests_mock_standby: Mocker
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.soundtouch.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: DEVICE_1_IP,
            },
        )

    assert len(mock_setup_entry.mock_calls) == 1

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == DEVICE_1_NAME
    assert result.get("data") == {
        CONF_HOST: DEVICE_1_IP,
    }
    assert "result" in result
    assert result["result"].unique_id == DEVICE_1_ID
    assert result["result"].title == DEVICE_1_NAME


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test a manual user flow with an invalid host."""
    requests_mock.get(ANY, exc=RequestException())

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={
            CONF_HOST: "invalid-hostname",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_flow_create_entry(
    hass: HomeAssistant, device1_requests_mock_standby: Mocker
) -> None:
    """Test the zeroconf flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            host=DEVICE_1_IP,
            addresses=[DEVICE_1_IP],
            port=8090,
            hostname="Bose-SM2-060000000001.local.",
            type="_soundtouch._tcp.local.",
            name=f"{DEVICE_1_NAME}._soundtouch._tcp.local.",
            properties={
                "DESCRIPTION": "SoundTouch",
                "MAC": DEVICE_1_ID,
                "MANUFACTURER": "Bose Corporation",
                "MODEL": "SoundTouch",
            },
        ),
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("description_placeholders") == {"name": DEVICE_1_NAME}

    with patch(
        "homeassistant.components.soundtouch.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert len(mock_setup_entry.mock_calls) == 1

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == DEVICE_1_NAME
    assert result.get("data") == {
        CONF_HOST: DEVICE_1_IP,
    }
    assert "result" in result
    assert result["result"].unique_id == DEVICE_1_ID
    assert result["result"].title == DEVICE_1_NAME
