"""Test the zwave_me config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.zwave_me.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
    FlowResult,
)

MOCK_ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    host="192.168.1.14",
    hostname="mock_hostname",
    name="mock_name",
    port=1234,
    properties={
        "deviceid": "aa:bb:cc:dd:ee:ff",
        "manufacturer": "fake_manufacturer",
        "model": "fake_model",
        "serialNumber": "fake_serial",
    },
    type="mock_type",
)


async def mock_uuid(url, _):
    """Mock getting uuid with proper UUID on 192.168.1.14 and None on others."""
    if "192.168.1.14" in url:
        return "12345678"
    else:
        return None


@patch("homeassistant.components.zwave_me.get_uuid", mock_uuid)
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.zwave_me.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "192.168.1.14",
                "token": "test-token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "ws://192.168.1.14"
    assert result2["data"] == {
        "url": "ws://192.168.1.14",
        "token": "test-token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.zwave_me.get_uuid", mock_uuid)
async def test_zeroconf(hass: HomeAssistant):
    """Test starting a flow from zeroconf."""
    with patch(
        "homeassistant.components.zwave_me.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=MOCK_ZEROCONF_DATA,
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "token": "test-token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "ws://192.168.1.14"
    assert result2["data"] == {
        "url": "ws://192.168.1.14",
        "token": "test-token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.zwave_me.get_uuid", mock_uuid)
async def test_error_handling_zeroconf(hass: HomeAssistant):
    """Test getting proper errors from no uuid."""
    data = MOCK_ZEROCONF_DATA
    data.host = "ws://192.12.12.12"
    with patch(
        "homeassistant.components.zwave_me.async_setup_entry",
        return_value=True,
    ):
        result: FlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=data,
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "no_valid_uuid_set"


@patch("homeassistant.components.zwave_me.get_uuid", mock_uuid)
async def test_handle_error_user(hass: HomeAssistant):
    """Test getting proper errors from no uuid."""
    with patch(
        "homeassistant.components.zwave_me.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "192.168.1.15",
                "token": "test-token",
            },
        )
        assert result2["errors"] == {"base": "no_valid_uuid_set"}
