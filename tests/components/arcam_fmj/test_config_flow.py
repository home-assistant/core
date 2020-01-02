"""Tests for the Arcam FMJ config flow module."""

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.arcam_fmj.config_flow import ArcamFmjFlowHandler
from homeassistant.components.arcam_fmj.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from .conftest import (
    MOCK_CONFIG,
    MOCK_CONFIG_ENTRY,
    MOCK_HOST,
    MOCK_NAME,
    MOCK_PORT,
    MOCK_UDN,
    MOCK_UUID,
)

from tests.common import MockConfigEntry

MOCK_UPNP_DEVICE = f"""
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <UDN>{MOCK_UDN}</UDN>
  </device>
</root>
"""

MOCK_UPNP_LOCATION = f"http://{MOCK_HOST}:8080/dd.xml"


@pytest.fixture(name="flow")
def flow_fixture(hass):
    """Create a mock flow for use in tests."""
    flow = ArcamFmjFlowHandler()
    flow.hass = hass
    flow.context = {}
    return flow


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock Arcam config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY, title=MOCK_NAME, unique_id=MOCK_UUID
    )


async def test_single_import_only(hass, flow, config_entry, aioclient_mock):
    """Test form is shown when host not provided."""
    aioclient_mock.get(MOCK_UPNP_LOCATION, text=MOCK_UPNP_DEVICE)
    config_entry.add_to_hass(hass)
    with pytest.raises(data_entry_flow.AbortFlow, match="Flow aborted: already_setup"):
        await flow.async_step_import(MOCK_CONFIG)


async def test_import(hass, flow, aioclient_mock):
    """Test form is shown when host not provided."""
    aioclient_mock.get(MOCK_UPNP_LOCATION, text=MOCK_UPNP_DEVICE)
    result = await flow.async_step_import(MOCK_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_UUID})"
    assert result["data"] == MOCK_CONFIG_ENTRY


async def test_import_upgrade(hass, flow, config_entry, aioclient_mock):
    """Test form is shown when host not provided."""
    aioclient_mock.get("http://localhost:8080/dd.xml", text=MOCK_UPNP_DEVICE)
    config_entry.add_to_hass(hass)
    config = dict(MOCK_CONFIG)
    config[CONF_HOST] = "localhost"
    with pytest.raises(
        data_entry_flow.AbortFlow, match="Flow aborted: updated_instance"
    ):
        await flow.async_step_import(config)


async def test_ssdp(hass, flow):
    """Test a ssdp import flow."""
    discover_data = {
        ssdp.ATTR_UPNP_MANUFACTURER: "ARCAM",
        ssdp.ATTR_UPNP_MODEL_NAME: " ",
        ssdp.ATTR_UPNP_MODEL_NUMBER: "AVR450, AVR750",
        ssdp.ATTR_UPNP_FRIENDLY_NAME: f"Arcam media client {MOCK_UUID}",
        ssdp.ATTR_UPNP_SERIAL: "12343",
        ssdp.ATTR_SSDP_LOCATION: f"http://{MOCK_HOST}:8080/dd.xml",
        ssdp.ATTR_UPNP_UDN: MOCK_UDN,
        ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:MediaRenderer:1",
    }

    result = await flow.async_step_ssdp(discover_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert flow.context["host"] == MOCK_HOST
    assert flow.unique_id == MOCK_UUID

    result = await flow.async_step_confirm({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_UUID})"
    assert result["data"] == MOCK_CONFIG_ENTRY


async def test_user(hass, flow, aioclient_mock):
    """Test a manual user configuration flow."""
    result = await flow.async_step_user(None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, text=MOCK_UPNP_DEVICE)
    result = await flow.async_step_user(user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_UUID})"
    assert result["data"] == MOCK_CONFIG_ENTRY


async def test_user_wrong(hass, flow, aioclient_mock):
    """Test a manual user configuration flow."""
    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, status=404)
    result = await flow.async_step_user(user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["base"] == "unique_identifier"
