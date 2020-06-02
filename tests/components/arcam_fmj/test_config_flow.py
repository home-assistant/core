"""Tests for the Arcam FMJ config flow module."""

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.arcam_fmj.config_flow import (
    ArcamFmjFlowHandler,
    get_entry_client,
)
from homeassistant.components.arcam_fmj.const import DOMAIN, DOMAIN_DATA_ENTRIES
from homeassistant.const import CONF_HOST, CONF_PORT

from .conftest import (
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

MOCK_DISCOVER = {
    ssdp.ATTR_UPNP_MANUFACTURER: "ARCAM",
    ssdp.ATTR_UPNP_MODEL_NAME: " ",
    ssdp.ATTR_UPNP_MODEL_NUMBER: "AVR450, AVR750",
    ssdp.ATTR_UPNP_FRIENDLY_NAME: f"Arcam media client {MOCK_UUID}",
    ssdp.ATTR_UPNP_SERIAL: "12343",
    ssdp.ATTR_SSDP_LOCATION: f"http://{MOCK_HOST}:8080/dd.xml",
    ssdp.ATTR_UPNP_UDN: MOCK_UDN,
    ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:MediaRenderer:1",
}


@pytest.fixture(name="flow")
def flow_fixture(hass):
    """Create a mock flow for use in tests."""
    flow = ArcamFmjFlowHandler()
    flow.hass = hass
    flow.context = {}
    return flow


async def test_ssdp(hass, flow):
    """Test a ssdp import flow."""
    result = await flow.async_step_ssdp(MOCK_DISCOVER)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert flow.context["host"] == MOCK_HOST
    assert flow.unique_id == MOCK_UUID

    result = await flow.async_step_confirm({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG_ENTRY


async def test_ssdp_abort(hass, flow):
    """Test a ssdp import flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY, title=MOCK_NAME, unique_id=MOCK_UUID
    )
    entry.add_to_hass(hass)

    with pytest.raises(
        data_entry_flow.AbortFlow, match="Flow aborted: already_configured"
    ):
        await flow.async_step_ssdp(MOCK_DISCOVER)


async def test_ssdp_update(hass, flow):
    """Test a ssdp import flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "old_host", CONF_PORT: MOCK_PORT},
        title=MOCK_NAME,
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with pytest.raises(
        data_entry_flow.AbortFlow, match="Flow aborted: already_configured"
    ):
        await flow.async_step_ssdp(MOCK_DISCOVER)
    assert entry.data[CONF_HOST] == MOCK_HOST


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
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG_ENTRY
    assert flow.unique_id == MOCK_UUID


async def test_invalid_ssdp(hass, flow, aioclient_mock):
    """Test a a config flow where ssdp fails."""
    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, text="")
    result = await flow.async_step_user(user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG_ENTRY
    assert flow.unique_id is None


async def test_user_wrong(hass, flow, aioclient_mock):
    """Test a manual user configuration flow with no ssdp response."""
    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, status=404)
    result = await flow.async_step_user(user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert flow.unique_id is None


async def test_get_entry_client(hass):
    """Test helper for configuration."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY, title=MOCK_NAME, unique_id=MOCK_UUID
    )
    hass.data[DOMAIN_DATA_ENTRIES] = {entry.entry_id: "dummy"}
    assert get_entry_client(hass, entry) == "dummy"
