"""Tests for Prana config flow."""

import pytest

from homeassistant.components.prana.config_flow import SERVICE_TYPE, PranaConfigFlow
from homeassistant.components.prana.const import CONF_CONFIG, CONF_MDNS
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_zeroconf_not_prana_device(hass: HomeAssistant) -> None:
    """If a non-Prana zeroconf is discovered, flow proceeds to confirm (no special filtering)."""
    flow = PranaConfigFlow()
    flow.hass = hass

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.10",
        ip_addresses=["192.168.1.10"],
        hostname="test.local",
        name="TestName._other._tcp.local.",
        type="_other._tcp.local.",
        port=1234,
        properties={},
    )

    result = await flow.async_step_zeroconf(info)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """If a config entry with the same unique_id already exists, discovery aborts as already_configured."""
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain="prana",
        title="Test Prana",
        data={
            "name": "Test Prana",
            "host": "127.0.0.1",
            "config": {"some_key": "some_value"},
            "mdns": "_prana._tcp.local._test",
        },
        source="user",
        entry_id="123456",
        options={},
        discovery_keys=None,
        unique_id="_prana._tcp.local._test",
        subentries_data=None,
    )
    entry.add_to_hass(hass)

    flow = PranaConfigFlow()
    flow.hass = hass

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.20",
        ip_addresses=["192.168.1.20"],
        hostname="test.local",
        name="_prana._tcp.local._test",
        type=SERVICE_TYPE,
        port=1234,
        properties={},
    )

    result = await flow.async_step_zeroconf(info)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_zeroconf_new_device_and_confirm(hass: HomeAssistant) -> None:
    """New device discovered via zeroconf shows confirm form and can be confirmed to create an entry."""
    flow = PranaConfigFlow()
    flow.hass = hass
    flow.context = {"source": "zeroconf"}

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.30",
        ip_addresses=["192.168.1.30"],
        hostname="prana.local",
        name="TestNew._prana._tcp.local.",
        type=SERVICE_TYPE,
        port=1234,
        properties={"label": "Prana Device", "config": {"mode": "eco"}},
    )

    # Zeroconf -> confirm form
    result = await flow.async_step_zeroconf(info)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Confirm -> create entry
    result2 = await flow.async_step_confirm(user_input={})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Prana Device"
    assert result2["data"][CONF_HOST] == "192.168.1.30"
    # CONF_CONFIG stores the properties object
    assert result2["data"][CONF_CONFIG] == {
        "label": "Prana Device",
        "config": {"mode": "eco"},
    }
    assert result2["data"][CONF_MDNS] == "TestNew._prana._tcp.local."


@pytest.mark.asyncio
async def test_confirm_abort_no_devices(hass: HomeAssistant) -> None:
    """Abort if confirm called without prior discovery information."""
    flow = PranaConfigFlow()
    flow.hass = hass

    result = await flow.async_step_confirm()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_user_flow_with_discovered_device(hass: HomeAssistant) -> None:
    """User flow should list discovered devices and allow choosing one."""
    # First, simulate zeroconf discovery to populate hass.data[DOMAIN + "_discovered"]
    flow_discover = PranaConfigFlow()
    flow_discover.hass = hass

    mdns_name = "DeviceOne._prana._tcp.local."
    info = ZeroconfServiceInfo(
        ip_address="192.168.1.40",
        ip_addresses=["192.168.1.40"],
        hostname="deviceone.local",
        name=mdns_name,
        type=SERVICE_TYPE,
        port=1234,
        properties={"label": "Device One", "config": {"mode": "auto"}},
    )

    # run zeroconf handler -> discovered stored (shows confirm)
    result = await flow_discover.async_step_zeroconf(info)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Now start a user flow which should present the discovered device
    flow_user = PranaConfigFlow()
    flow_user.hass = hass

    # Initial call returns a form listing choices
    result_user = await flow_user.async_step_user()
    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    # Submit the selected mdns to create the entry
    result_create = await flow_user.async_step_user(user_input={"mdns": mdns_name})
    assert result_create["type"] == FlowResultType.CREATE_ENTRY
    assert result_create["title"] == "Device One"
    assert result_create["data"][CONF_HOST] == "192.168.1.40"
    assert result_create["data"][CONF_MDNS] == mdns_name
    assert result_create["data"][CONF_CONFIG] == {
        "label": "Device One",
        "config": {"mode": "auto"},
    }


@pytest.mark.asyncio
async def test_user_flow_when_no_discovered_devices_shows_manual(
    hass: HomeAssistant,
) -> None:
    """If no devices were discovered, user flow forwards to manual step (form)."""
    flow = PranaConfigFlow()
    flow.hass = hass

    # Ensure no discovered devices in hass.data
    hass.data.pop("prana_discovered", None)

    result = await flow.async_step_user()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"
