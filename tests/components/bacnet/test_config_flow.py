"""Tests for the BACnet config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet import BACnetHubRuntimeData
from homeassistant.components.bacnet.bacnet_client import BACnetDeviceInfo
from homeassistant.components.bacnet.const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_ENTRY_TYPE,
    CONF_HUB_ID,
    CONF_INTERFACE,
    DOMAIN,
    ENTRY_TYPE_DEVICE,
    ENTRY_TYPE_HUB,
)
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MOCK_DEVICE_ADDRESS,
    MOCK_DEVICE_ID,
    MOCK_LISTEN_ADDRESS,
    create_mock_hub_config_entry,
    init_integration_with_hub,
)

from tests.common import MockConfigEntry


async def test_create_hub_with_interface_selection(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test creating a BACnet hub by selecting an interface."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_INTERFACE in result["data_schema"].schema

    # Verify get_local_interfaces was called
    mock_get_local_interfaces.assert_called_once()

    # Select an interface (interface name, not IP)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "eth0"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BACnet Client (eth0)"
    assert result["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_HUB
    assert result["data"][CONF_INTERFACE] == "eth0"


async def test_create_hub_with_manual_ip_address(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test creating a BACnet hub with manual IP address entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_interface"

    # Enter IP address manually (stored as-is since it's manual)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "192.168.1.50"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BACnet Client (192.168.1.50)"
    assert result["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_HUB
    assert result["data"][CONF_INTERFACE] == "192.168.1.50"


async def test_create_hub_manual_invalid_ip(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test manual IP address entry with invalid IP."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    # Enter invalid IP address
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "not.an.ip.address"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_interface"
    assert result["errors"] == {"base": "invalid_ip"}


async def test_create_hub_with_listen_all(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test creating a BACnet hub with 0.0.0.0 (listen on all interfaces)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "0.0.0.0"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BACnet Client (0.0.0.0)"
    assert result["data"][CONF_INTERFACE] == "0.0.0.0"


async def test_hub_already_exists_redirects_to_add_device(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that when hub exists, user is redirected to add device flow."""
    # Create existing hub (don't need to set it up for config flow test)
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    # Set up runtime_data manually for config flow to access

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id=f"bacnet_client_{MOCK_LISTEN_ADDRESS.replace('.', '_')}",
    )

    # Start user flow again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Should be redirected to add device flow instead
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discover"

    # Wait for discovery task to complete and then abort the flow to avoid
    # teardown errors from an unfinished show_progress flow
    await hass.async_block_till_done()
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_add_device_discover_and_select(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test discovering devices and selecting one to add."""
    # Create hub first
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id=f"bacnet_client_{MOCK_LISTEN_ADDRESS.replace('.', '_')}",
    )

    # Start add device flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Should show progress for discovery
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discover"

    # Wait for discovery to complete
    await hass.async_block_till_done()

    # Progress should be done, form should appear
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should now show form with discovered devices (after async_show_progress_done)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"

    # Select a device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_ID: str(MOCK_DEVICE_ID)},
    )

    # Should show progress for object discovery
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discover_objects"

    # Wait for object discovery to complete
    await hass.async_block_till_done()

    # Get result
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show sensor selection form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sensors"

    # Select sensors (or all by default)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    # Should create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test HVAC Controller"
    assert result["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_DEVICE
    assert result["data"][CONF_DEVICE_ID] == MOCK_DEVICE_ID
    assert result["data"][CONF_DEVICE_ADDRESS] == MOCK_DEVICE_ADDRESS
    assert result["data"][CONF_HUB_ID] == hub_entry.entry_id


async def test_discover_no_devices(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that an error is shown when no devices are found."""
    mock_bacnet_client.discover_devices.return_value = []

    # Create hub first
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id=f"bacnet_client_{MOCK_LISTEN_ADDRESS.replace('.', '_')}",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Wait for discovery
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}


async def test_discover_timeout(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test handling of discovery timeout."""
    mock_bacnet_client.discover_devices.side_effect = TimeoutError

    # Create hub first
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id=f"bacnet_client_{MOCK_LISTEN_ADDRESS.replace('.', '_')}",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Wait for discovery
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "discovery_timeout"}


async def test_already_configured_device(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that duplicate devices are not added."""
    # Create hub
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id=f"bacnet_client_{MOCK_LISTEN_ADDRESS.replace('.', '_')}",
    )

    # Create existing device
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(MOCK_DEVICE_ID),
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
            CONF_DEVICE_ID: MOCK_DEVICE_ID,
            CONF_DEVICE_ADDRESS: MOCK_DEVICE_ADDRESS,
            CONF_HUB_ID: hub_entry.entry_id,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Wait for discovery
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_ID: str(MOCK_DEVICE_ID)},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_interfaces_found(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test error when no network interfaces are found."""
    mock_get_local_interfaces.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_interfaces"}


async def test_multiple_devices_discovered(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that multiple discovered devices each get their own discovery flow."""

    # Create multiple mock devices with different IDs
    mock_devices = [
        BACnetDeviceInfo(
            device_id=1234,
            address="192.168.1.100:47808",
            name="HVAC Controller",
            vendor_name="Vendor A",
            model_name="Model X",
        ),
        BACnetDeviceInfo(
            device_id=5678,
            address="192.168.1.101:47808",
            name="Lighting Controller",
            vendor_name="Vendor B",
            model_name="Model Y",
        ),
        BACnetDeviceInfo(
            device_id=9999,
            address="192.168.1.102:47808",
            name="Access Controller",
            vendor_name="Vendor C",
            model_name="Model Z",
        ),
    ]
    mock_bacnet_client.discover_devices.return_value = mock_devices

    # Create and set up hub
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "eth0"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    _ = result["result"]

    # Wait for initial discovery to complete
    await hass.async_block_till_done()

    # Get all in-progress discovery flows
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    discovery_flows = [
        flow
        for flow in flows
        if flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    ]

    # Should have created 3 discovery flows, one per device
    assert len(discovery_flows) == 3

    # Verify each flow has unique ID and correct data
    flow_unique_ids = {flow["context"]["unique_id"] for flow in discovery_flows}
    assert flow_unique_ids == {"1234", "5678", "9999"}

    # Verify title placeholders are set correctly for each flow (with IP addresses)
    flow_titles = {
        flow["context"]["title_placeholders"]["name"] for flow in discovery_flows
    }
    assert "HVAC Controller (192.168.1.100)" in flow_titles
    assert "Lighting Controller (192.168.1.101)" in flow_titles
    assert "Access Controller (192.168.1.102)" in flow_titles


async def test_discovery_ignores_already_configured_devices(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that discovery doesn't create flows for already configured devices."""

    # Create multiple mock devices
    mock_devices = [
        BACnetDeviceInfo(
            device_id=1234,
            address="192.168.1.100:47808",
            name="HVAC Controller",
            vendor_name="Vendor A",
            model_name="Model X",
        ),
        BACnetDeviceInfo(
            device_id=5678,
            address="192.168.1.101:47808",
            name="Lighting Controller",
            vendor_name="Vendor B",
            model_name="Model Y",
        ),
    ]
    mock_bacnet_client.discover_devices.return_value = mock_devices

    # Add one device as already configured (before creating hub so initial discovery skips it)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_DEVICE,
            CONF_DEVICE_ID: 1234,
            CONF_DEVICE_ADDRESS: "192.168.1.100:47808",
        },
    ).add_to_hass(hass)

    # Create hub
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "eth0"},
    )
    _ = result["result"]

    # Wait for initial discovery to complete
    await hass.async_block_till_done()

    # Get all in-progress discovery flows
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    discovery_flows = [
        flow
        for flow in flows
        if flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    ]

    # Should only create 1 discovery flow (for device 5678, not 1234)
    assert len(discovery_flows) == 1
    assert discovery_flows[0]["context"]["unique_id"] == "5678"


async def test_integration_discovery_confirm(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test the integration discovery confirm step creates an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_DEVICE_ID: MOCK_DEVICE_ID,
            CONF_DEVICE_ADDRESS: MOCK_DEVICE_ADDRESS,
            CONF_HUB_ID: "hub_entry_id_123",
            "name": "Test Device",
            "vendor_name": "TestVendor",
            "model_name": "ModelA",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"

    # Confirm the discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device"
    assert result["data"][CONF_ENTRY_TYPE] == ENTRY_TYPE_DEVICE
    assert result["data"][CONF_DEVICE_ID] == MOCK_DEVICE_ID
    assert result["data"][CONF_DEVICE_ADDRESS] == MOCK_DEVICE_ADDRESS
    assert result["data"][CONF_HUB_ID] == "hub_entry_id_123"


async def test_integration_discovery_vendor_only(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test integration discovery with only vendor name (no model)."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_DEVICE_ID: 9999,
            CONF_DEVICE_ADDRESS: "10.0.0.1:47808",
            CONF_HUB_ID: "hub_123",
            "name": "Simple Device",
            "vendor_name": "VendorOnly",
            "model_name": "",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"


async def test_integration_discovery_model_only(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test integration discovery with only model name (no vendor)."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_DEVICE_ID: 8888,
            CONF_DEVICE_ADDRESS: "10.0.0.2:47808",
            CONF_HUB_ID: "hub_123",
            "name": "",
            "vendor_name": "",
            "model_name": "ModelOnly",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "integration_discovery_confirm"


async def test_manual_ip_0000(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test manual IP entry with 0.0.0.0."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "0.0.0.0"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INTERFACE] == "0.0.0.0"


async def test_manual_ip_empty(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test manual IP entry with empty string shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_ip"}


async def test_get_interfaces_exception(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test error handling when get_local_interfaces raises an exception."""
    mock_get_local_interfaces.side_effect = RuntimeError("network error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_discover_generic_exception(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test handling of generic exception during discovery."""
    mock_bacnet_client.discover_devices.side_effect = RuntimeError("connection failed")

    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id="bacnet_client_eth0",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_discover_objects_timeout(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test handling of timeout during object discovery."""
    # First discover devices normally, then fail on object discovery
    mock_bacnet_client.get_device_objects.side_effect = TimeoutError

    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    hub_entry.runtime_data = BACnetHubRuntimeData(
        client=mock_bacnet_client,
        hub_device_id="bacnet_client_eth0",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Wait for device discovery
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"

    # Select a device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_ID: str(MOCK_DEVICE_ID)},
    )

    # Should start object discovery
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discover_objects"

    # Wait for object discovery (which will timeout)
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show error form
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "discovery_timeout"}


async def test_reconfigure_hub(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a hub entry."""
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hub_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "10.0.0.5"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert hub_entry.data[CONF_INTERFACE] == "10.0.0.5"


async def test_reconfigure_hub_invalid_ip(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a hub entry with an invalid IP."""
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    result = await hub_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "not-valid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_INTERFACE: "invalid_ip"}


async def test_reconfigure_device(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a device entry."""

    _, device_entry = await init_integration_with_hub(hass)

    result = await device_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_ADDRESS: "10.0.0.50:47808"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert device_entry.data[CONF_DEVICE_ADDRESS] == "10.0.0.50:47808"


async def test_reconfigure_device_empty_address(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a device with empty address shows error."""

    _, device_entry = await init_integration_with_hub(hass)

    result = await device_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DEVICE_ADDRESS: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_ADDRESS: "cannot_connect"}


async def test_options_flow_shows_objects(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test options flow shows object selection form."""

    _, device_entry = await init_integration_with_hub(hass)

    result = await hass.config_entries.options.async_init(device_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_save_selection(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test options flow saves selected objects."""

    _, device_entry = await init_integration_with_hub(hass)

    result = await hass.config_entries.options.async_init(device_entry.entry_id)

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"selected_objects": ["analog-input,0", "analog-input,1"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["selected_objects"] == [
        "analog-input,0",
        "analog-input,1",
    ]


async def test_discover_no_hub_aborts(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that discovery aborts when no hub is found."""
    # Create an existing hub entry but don't add it to hass
    # Simulate hub being present so we go to discover, but then
    # no hub_entry_id is set (edge case)
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)

    # Start flow - this should redirect to add_device_select_hub
    # Then discover should try to use the hub, but runtime_data isn't set
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Since hub exists but has no runtime_data, should abort
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "hub_not_ready"
