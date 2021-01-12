"""Tests for the AV Receiver config flow."""
from unittest.mock import patch
from urllib.parse import urlparse

from pyavreceiver.error import AVReceiverIncompatibleDeviceError

from homeassistant import data_entry_flow
from homeassistant.components import avreceiver, ssdp
from homeassistant.components.avreceiver.config_flow import AVReceiverFlowHandler
from homeassistant.components.avreceiver.const import DATA_DISCOVERED_HOSTS, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_ID


async def test_no_host_shows_form(hass):
    """Test form is shown when host not provided."""
    flow = AVReceiverFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_cannot_connect_shows_error_form(hass, controller):
    """Test form is shown with error when cannot connect."""
    controller.init.side_effect = AVReceiverIncompatibleDeviceError()
    result = await hass.config_entries.flow.async_init(
        avreceiver.DOMAIN, context={"source": "user"}, data={CONF_HOST: "127.0.0.1"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"][CONF_HOST] == "cannot_connect"
    assert controller.init.call_count == 1
    assert controller.disconnect.call_count == 0
    controller.init.reset_mock()
    controller.disconnect.reset_mock()


async def test_create_entry_when_host_valid(hass, controller):
    """Test result type is create entry when host is valid."""
    data = {CONF_HOST: "127.0.0.1", CONF_ID: "avreceiver-serial"}
    with patch(
        "homeassistant.components.avreceiver.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            avreceiver.DOMAIN, context={"source": "user"}, data=data
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["result"].unique_id == f"{avreceiver.DOMAIN}-serial"
        assert result["title"] == "AV Receiver (127.0.0.1)"
        assert result["data"] == data
        assert controller.init.call_count == 1
        assert controller.disconnect.call_count == 1
        controller.init.reset_mock()
        controller.disconnect.reset_mock()


async def test_create_two_entries_when_hosts_valid(hass, controller):
    """Test result type is create entry when host is valid."""
    data = {CONF_HOST: "127.0.0.1", CONF_ID: "avreceiver-serial"}
    data2 = {CONF_HOST: "127.0.0.2", CONF_ID: "avreceiver-serial"}
    with patch(
        "homeassistant.components.avreceiver.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            avreceiver.DOMAIN, context={"source": "user"}, data=data
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "AV Receiver (127.0.0.1)"
        assert result["data"] == data

        result = await hass.config_entries.flow.async_init(
            avreceiver.DOMAIN, context={"source": "user"}, data=data2
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "AV Receiver (127.0.0.2)"
        assert result["data"] == data2


async def test_config_flow_aborts_when_hosts_match(hass, controller):
    """Test result type is create entry when host is valid."""
    data = {CONF_HOST: "127.0.0.1"}
    data2 = {CONF_HOST: "127.0.0.1"}
    with patch(
        "homeassistant.components.avreceiver.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            avreceiver.DOMAIN, context={"source": "user"}, data=data
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        result = await hass.config_entries.flow.async_init(
            avreceiver.DOMAIN, context={"source": "user"}, data=data2
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "single_instance_allowed"


async def test_create_entry_when_friendly_name_valid(hass, controller):
    """Test result type is create entry when friendly name is valid."""
    hass.data[DATA_DISCOVERED_HOSTS] = {"Office (127.0.0.1)": "127.0.0.1"}
    data = {CONF_HOST: "127.0.0.1"}
    with patch(
        "homeassistant.components.avreceiver.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            avreceiver.DOMAIN, context={"source": "user"}, data=data
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["result"].unique_id == f"{avreceiver.DOMAIN}-serial"
        assert result["title"] == "AV Receiver (127.0.0.1)"
        assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_ID: "avreceiver-serial"}
        assert controller.init.call_count == 1
        assert controller.disconnect.call_count == 1
        assert DATA_DISCOVERED_HOSTS not in hass.data


async def test_discovery_shows_create_form(hass, controller, discovery_data):
    """Test discovery shows form to confirm setup and subsequent abort."""
    await hass.config_entries.flow.async_init(
        avreceiver.DOMAIN, context={"source": "ssdp"}, data=discovery_data
    )
    await hass.async_block_till_done()
    flows_in_progress = hass.config_entries.flow.async_progress()
    assert flows_in_progress[0]["context"]["unique_id"] == f"{DOMAIN}-serial"
    assert len(flows_in_progress) == 1
    assert hass.data[DATA_DISCOVERED_HOSTS] == {"Office (127.0.0.1)": "127.0.0.1"}

    port = urlparse(discovery_data[ssdp.ATTR_SSDP_LOCATION]).port
    discovery_data[ssdp.ATTR_SSDP_LOCATION] = f"http://127.0.0.2:{port}/"
    discovery_data[ssdp.ATTR_UPNP_FRIENDLY_NAME] = "Bedroom"

    await hass.config_entries.flow.async_init(
        avreceiver.DOMAIN, context={"source": "ssdp"}, data=discovery_data
    )
    await hass.async_block_till_done()
    flows_in_progress = hass.config_entries.flow.async_progress()
    assert flows_in_progress[0]["context"]["unique_id"] == f"{DOMAIN}-serial"
    assert len(flows_in_progress) == 1
    assert hass.data[DATA_DISCOVERED_HOSTS] == {
        "Office (127.0.0.1)": "127.0.0.1",
        "Bedroom (127.0.0.2)": "127.0.0.2",
    }


async def test_discovery_flow_aborts_already_setup(
    hass, controller, discovery_data, config_entry
):
    """Test discovery flow aborts when entry already setup."""
    config_entry.add_to_hass(hass)
    flow = AVReceiverFlowHandler()
    flow.hass = hass
    result = await flow.async_step_ssdp(discovery_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_discovery_sets_the_unique_id(hass, controller, discovery_data):
    """Test discovery sets the unique id."""
    port = urlparse(discovery_data[ssdp.ATTR_SSDP_LOCATION]).port
    discovery_data[ssdp.ATTR_SSDP_LOCATION] = f"http://127.0.0.2:{port}/"
    discovery_data[ssdp.ATTR_UPNP_FRIENDLY_NAME] = "Bedroom"

    await hass.config_entries.flow.async_init(
        avreceiver.DOMAIN, context={"source": SOURCE_SSDP}, data=discovery_data
    )
    await hass.async_block_till_done()
    flows_in_progress = hass.config_entries.flow.async_progress()
    assert flows_in_progress[0]["context"]["unique_id"] == f"{DOMAIN}-serial"
    assert len(flows_in_progress) == 1
    assert hass.data[DATA_DISCOVERED_HOSTS] == {"Bedroom (127.0.0.2)": "127.0.0.2"}
