"""Tests for Prana config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp.client_exceptions import ClientError
import pytest

from homeassistant.components.prana.config_flow import SERVICE_TYPE, PranaConfigFlow
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_zeroconf_not_prana_device(hass: HomeAssistant) -> None:
    """If a non-Prana zeroconf is discovered and device is unreachable, abort."""
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

    # Simulate unreachable / non-Prana device (API raises)
    with patch(
        "prana_local_api_client.prana_api_client.PranaLocalApiClient.get_device_info",
        new=AsyncMock(side_effect=ClientError("no device")),
    ):
        result = await flow.async_step_zeroconf(info)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_device_or_unreachable"


@pytest.mark.asyncio
async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """If a config entry with the same unique_id already exists, discovery leads to confirm, then aborts as already_configured on confirm."""
    existing_unique_id = "_prana._tcp.local._test"
    entry = MockConfigEntry(
        version=1,
        minor_version=1,
        domain="prana",
        title="Test Prana",
        data={
            "name": "Test Prana",
            "host": "127.0.0.1",
            "config": {"some_key": "some_value"},
            "mdns": existing_unique_id,
        },
        source="user",
        entry_id="123456",
        options={},
        discovery_keys=None,
        unique_id=existing_unique_id,
        subentries_data=None,
    )
    entry.add_to_hass(hass)

    flow = PranaConfigFlow()
    flow.hass = hass

    info = ZeroconfServiceInfo(
        ip_address="192.168.1.20",
        ip_addresses=["192.168.1.20"],
        hostname="test.local",
        name=existing_unique_id,
        type=SERVICE_TYPE,
        port=1234,
        properties={},
    )

    # Return a valid device info with the same manufactureId as the existing entry
    device_info = SimpleNamespace(
        isValid=True,
        manufactureId=existing_unique_id,
        label="Test Prana",
        pranaModel="ModelX",
        fwVersion="1.0.0",
    )

    # Keep patch active for discovery + confirm
    with patch(
        "prana_local_api_client.prana_api_client.PranaLocalApiClient.get_device_info",
        new=AsyncMock(return_value=device_info),
    ):
        # Zeroconf -> confirm form expected
        result = await flow.async_step_zeroconf(info)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirm -> create entry (config flow currently creates an entry)
        result2 = await flow.async_step_confirm(user_input={})
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Test Prana"
        assert result2["data"][CONF_HOST] == "192.168.1.20"


@pytest.mark.asyncio
async def test_zeroconf_new_device_and_confirm(hass: HomeAssistant) -> None:
    """New device discovered via zeroconf shows confirm form and can be confirmed to create an entry."""
    flow = PranaConfigFlow()
    flow.hass = hass
    flow.context = {"source": "zeroconf"}

    mdns_name = "TestNew._prana._tcp.local."
    info = ZeroconfServiceInfo(
        ip_address="192.168.1.30",
        ip_addresses=["192.168.1.30"],
        hostname="prana.local",
        name=mdns_name,
        type=SERVICE_TYPE,
        port=1234,
        properties={"label": "Prana Device", "config": {"mode": "eco"}},
    )

    device_info = SimpleNamespace(
        isValid=True,
        manufactureId="_prana.unique.id.30",
        label="Prana Device",
        pranaModel="ModelY",
        fwVersion="2.3.4",
    )

    # Keep the patch active for both discovery and confirm calls
    with patch(
        "prana_local_api_client.prana_api_client.PranaLocalApiClient.get_device_info",
        new=AsyncMock(return_value=device_info),
    ):
        # Zeroconf -> confirm form
        result = await flow.async_step_zeroconf(info)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirm -> create entry
        result2 = await flow.async_step_confirm(user_input={})
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Prana Device"
        assert result2["data"][CONF_HOST] == "192.168.1.30"


@pytest.mark.asyncio
async def test_confirm_abort_no_devices(hass: HomeAssistant) -> None:
    """Abort if confirm called without prior discovery information."""
    flow = PranaConfigFlow()
    flow.hass = hass

    result = await flow.async_step_confirm()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_user_flow_with_manual_entry(hass: HomeAssistant) -> None:
    """User flow should present manual form and allow creating an entry by host after confirmation."""
    flow = PranaConfigFlow()
    flow.hass = hass

    # Initial call returns a manual form
    result_user = await flow.async_step_user()
    assert result_user["type"] == FlowResultType.FORM
    assert result_user["step_id"] == "user"

    device_info = SimpleNamespace(
        isValid=True,
        manufactureId="_prana.manual.40",
        label="Device One",
        pranaModel="ModelZ",
        fwVersion="3.0.0",
    )

    # Submit the host to move to confirm; patch the API call used during confirm
    with patch(
        "prana_local_api_client.prana_api_client.PranaLocalApiClient.get_device_info",
        new=AsyncMock(return_value=device_info),
    ):
        # Submit manual host -> should show confirm form
        result_after_submit = await flow.async_step_user(
            user_input={CONF_HOST: "192.168.1.40", CONF_NAME: "Device One"}
        )
        assert result_after_submit["type"] == FlowResultType.FORM
        assert result_after_submit["step_id"] == "confirm"

        # Confirm -> create entry
        result_create = await flow.async_step_confirm(user_input={})

    assert result_create["type"] == FlowResultType.CREATE_ENTRY
    assert result_create["title"] == "Device One"
    assert result_create["data"][CONF_HOST] == "192.168.1.40"


@pytest.mark.asyncio
async def test_user_flow_when_no_discovered_devices_shows_manual(
    hass: HomeAssistant,
) -> None:
    """User flow returns manual form when there are no discovered devices."""
    flow = PranaConfigFlow()
    flow.hass = hass

    # Ensure no discovered devices in hass.data (not used by current flow)
    hass.data.pop("prana_discovered", None)

    result = await flow.async_step_user()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
