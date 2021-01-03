"""Test the devolo Home Network config flow."""
from devolo_plc_api.exceptions.device import DeviceNotFound

from homeassistant import config_entries, setup
from homeassistant.components.devolo_home_network import config_flow
from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.const import CONF_BASE, CONF_IP_ADDRESS
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import DISCOVERY_INFO, DISCOVERY_INFO_WRONG_DEVICE, IP

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    info = {
        # TODO Use constants
        "serial_number": "1234567890",
        "title": "device name",
    }

    with patch(
        "homeassistant.components.devolo_home_network.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.devolo_home_network.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.devolo_home_network.config_flow.validate_input",
        return_value=info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: IP,
            },
        )
        await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == info["title"]
    assert result2["data"] == {
        CONF_IP_ADDRESS: IP,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.devolo_home_network.config_flow.validate_input",
        side_effect=DeviceNotFound,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: IP,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {CONF_BASE: "cannot_connect"}


async def test_show_zeroconf_form(hass):
    """Test that the zeroconf confirmation form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["description_placeholders"] == {"host_name": "test"}


async def test_abort_zeroconf_no_discovery(hass):
    """Test we abort zeroconf on missing discovery info."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=None
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_abort_zeroconf_wrong_device(hass):
    """Test we abort zeroconf for wrong devices."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_WRONG_DEVICE,
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "devolo Home Control Gateway"


async def test_step_zeroconf_confirm(hass):
    """Test zeroconf confirmation with user input."""
    flow = config_flow.ConfigFlow()
    flow._discovery_info = DISCOVERY_INFO
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await flow.async_step_zeroconf_confirm(user_input={})
    assert result["title"] == "test"
    assert result["data"] == {
        CONF_IP_ADDRESS: IP,
    }
