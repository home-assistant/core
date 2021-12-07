"""Test the zwave_me config flow."""
from unittest.mock import patch, Mock

from homeassistant import config_entries
from homeassistant.components.zwave_me.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.const import CONF_HOST
from homeassistant.components import zeroconf

MOCK_ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    host="fake_host",
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


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zwave_me.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "url": "192.168.1.14",
                "token": "test-token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == result2["url"]
    assert result2["data"] == {
        "url": "192.168.1.14",
        "token": "test-token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf(hass: HomeAssistant, remote: Mock, remotews: Mock):
    """Test starting a flow from zeroconf."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    await hass.async_block_till_done()
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input="whatever"
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "1.1.1.1"
    assert result["data"][CONF_HOST] == "1.1.1.1"
