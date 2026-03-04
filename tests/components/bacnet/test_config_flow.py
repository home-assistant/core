"""Tests for the BACnet config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DEVICE_INSTANCE,
    CONF_DEVICES,
    CONF_INTERFACE,
    CONF_SELECTED_OBJECTS,
    DEFAULT_PORT,
    DEVICE_INSTANCE_MAX,
    DEVICE_INSTANCE_MIN,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MOCK_DEVICE_ADDRESS,
    MOCK_DEVICE_ID,
    MOCK_LISTEN_ADDRESS,
    create_mock_hub_config_entry,
    create_mock_hub_only_config_entry,
)

from tests.common import MockConfigEntry

# --- Hub creation tests ---


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
    assert result["title"] == "BACnet Client (eth0 192.168.21.0-192.168.21.255)"
    assert result["data"][CONF_INTERFACE] == "eth0"
    assert result["data"][CONF_DEVICES] == {}
    assert (
        DEVICE_INSTANCE_MIN
        <= result["data"][CONF_DEVICE_INSTANCE]
        <= DEVICE_INSTANCE_MAX
    )


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


async def test_create_hub_already_in_use(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that creating a hub with an already-used interface aborts."""
    # Set up an existing hub on eth0
    existing = create_mock_hub_only_config_entry()
    existing.add_to_hass(hass)
    await hass.config_entries.async_setup(existing.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Try to use the already-used interface
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: MOCK_LISTEN_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_hub_creation_includes_empty_devices(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that hub creation always includes an empty devices dict."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "eth0"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_DEVICES in result["data"]
    assert result["data"][CONF_DEVICES] == {}


# --- Add device subentry tests (manual entry) ---


async def test_add_device_subentry_manual(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test adding a BACnet device via the subentry flow (manual entry)."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Enter device address
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "192.168.1.100",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    # Verify device was added to hub entry data
    devices = entry.data[CONF_DEVICES]
    assert str(MOCK_DEVICE_ID) in devices
    device_config = devices[str(MOCK_DEVICE_ID)]
    assert device_config[CONF_DEVICE_ID] == MOCK_DEVICE_ID
    assert device_config[CONF_SELECTED_OBJECTS] == []

    # Verify directed discovery was called
    mock_bacnet_client.discover_device_at_address.assert_called_once_with(
        "192.168.1.100", timeout=5
    )


async def test_add_device_subentry_custom_port(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test adding a BACnet device with a custom port via subentry flow."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "10.0.0.5",
            "port": 47809,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    # Verify directed discovery used the custom port
    mock_bacnet_client.discover_device_at_address.assert_called_once_with(
        "10.0.0.5:47809", timeout=5
    )


async def test_add_device_subentry_invalid_ip(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test adding a device with an invalid IP address shows error."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "not-an-ip",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {CONF_DEVICE_ADDRESS: "invalid_ip"}


async def test_add_device_subentry_not_found(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test error when no device responds at the given address."""
    mock_bacnet_client.discover_device_at_address.return_value = None

    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "192.168.1.200",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "device_not_found_at_address"}


async def test_add_device_subentry_connection_error(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test error when discovery raises an exception."""
    mock_bacnet_client.discover_device_at_address.side_effect = RuntimeError(
        "network error"
    )

    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "192.168.1.100",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_add_device_subentry_already_configured(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that adding an already-configured device aborts."""
    # Hub with an existing device
    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Clear discovered devices so flow goes straight to manual step
    entry.runtime_data.discovered_devices = []

    # The mock client returns device with MOCK_DEVICE_ID which is already configured
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "192.168.1.100",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_add_device_subentry_hub_not_loaded(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that add device aborts when hub entry is not loaded."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)

    # Don't set up the entry - it stays NOT_LOADED
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "hub_not_ready"


# --- Discovery flow tests ---


async def test_discovery_flow_adds_device(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that a discovery flow adds a device to the hub when confirmed."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_DEVICE_ID: 5678,
            CONF_DEVICE_ADDRESS: "192.168.1.200:47808",
            "device_name": "Discovered HVAC",
            "hub_entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Confirm the discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"

    # Verify device was added to hub entry data
    devices = entry.data[CONF_DEVICES]
    assert "5678" in devices
    assert devices["5678"][CONF_DEVICE_ID] == 5678
    assert devices["5678"][CONF_DEVICE_ADDRESS] == "192.168.1.200:47808"
    assert devices["5678"][CONF_SELECTED_OBJECTS] == []


async def test_discovery_flow_already_configured(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that discovery aborts if the device is already configured."""
    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_DEVICE_ID: MOCK_DEVICE_ID,
            CONF_DEVICE_ADDRESS: MOCK_DEVICE_ADDRESS,
            "device_name": "Already Configured",
            "hub_entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- Reconfigure tests ---


async def test_reconfigure_hub(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a hub entry by selecting a different interface."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Select a different interface from the dropdown
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "wlan0"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_INTERFACE] == "wlan0"


async def test_reconfigure_hub_manual_ip(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a hub entry with manual IP address entry."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_manual"

    # Enter a valid IP address
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "10.0.0.5"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_INTERFACE] == "10.0.0.5"


async def test_reconfigure_hub_manual_invalid_ip(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfiguring a hub entry with an invalid manual IP."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    # Enter invalid IP
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "not-valid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_manual"
    assert result["errors"] == {"base": "invalid_ip"}


async def test_reconfigure_hub_already_in_use(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that reconfiguring to an already-used interface shows error."""
    # Create two hub entries
    entry1 = create_mock_hub_only_config_entry()
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="BACnet Client (wlan0)",
        data={CONF_INTERFACE: "wlan0", CONF_DEVICES: {}},
    )
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    # Try to reconfigure entry2 to use eth0 (already used by entry1)
    result = await entry2.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: MOCK_LISTEN_ADDRESS},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_in_use"}


async def test_reconfigure_hub_manual_already_in_use(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that manual reconfigure to an already-used IP shows error."""
    # Create two hub entries
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="BACnet Client (10.0.0.5)",
        data={CONF_INTERFACE: "10.0.0.5", CONF_DEVICES: {}},
    )
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    entry2 = create_mock_hub_only_config_entry()
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    # Reconfigure entry2 via manual to use 10.0.0.5 (taken by entry1)
    result = await entry2.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "manual"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: "10.0.0.5"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_in_use"}


async def test_reconfigure_same_interface_allowed(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that reconfiguring to the same interface succeeds (not a duplicate)."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)

    # Select the same interface the entry already uses
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_INTERFACE: MOCK_LISTEN_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


# --- Discovery flow edge case tests ---


async def test_discovery_flow_hub_not_ready_on_confirm(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test discovery confirm aborts when hub entry no longer exists."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_DEVICE_ID: 5678,
            CONF_DEVICE_ADDRESS: "192.168.1.200:47808",
            "device_name": "Discovered HVAC",
            "hub_entry_id": "nonexistent_entry_id",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Confirm — hub entry doesn't exist
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "hub_not_ready"


async def test_discovery_confirm_device_added_while_pending(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test discovery confirm aborts if device was added while flow was pending."""
    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Start a discovery flow for a NEW device (not MOCK_DEVICE_ID)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_DEVICE_ID: 5678,
            CONF_DEVICE_ADDRESS: "192.168.1.200:47808",
            "device_name": "Discovered HVAC",
            "hub_entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM

    # Simulate device being added by another flow while this one was pending
    devices = dict(entry.data.get(CONF_DEVICES, {}))
    devices["5678"] = {
        CONF_DEVICE_ID: 5678,
        CONF_DEVICE_ADDRESS: "192.168.1.200:47808",
        CONF_SELECTED_OBJECTS: [],
    }
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_DEVICES: devices},
    )

    # Confirm — device already configured
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_validate_ip_empty_string(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that empty IP address returns invalid_ip error."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_ADDRESS: "invalid_ip"}


async def test_validate_ip_zero_address(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that 0.0.0.0 address returns invalid_ip error."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "0.0.0.0",
            "port": DEFAULT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_DEVICE_ADDRESS: "invalid_ip"}


async def test_add_device_subentry_aborts_discovery_flow(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that adding a device via subentry aborts its pending discovery flow."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Start a discovery flow for the same device the mock client returns
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_DEVICE_ID: MOCK_DEVICE_ID,
            CONF_DEVICE_ADDRESS: MOCK_DEVICE_ADDRESS,
            "device_name": "Discovered HVAC",
            "hub_entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM

    # Add the same device via subentry
    sub_result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": SOURCE_USER},
    )

    sub_result = await hass.config_entries.subentries.async_configure(
        sub_result["flow_id"],
        user_input={
            CONF_DEVICE_ADDRESS: "192.168.1.100",
            "port": DEFAULT_PORT,
        },
    )

    assert sub_result["type"] is FlowResultType.ABORT
    assert sub_result["reason"] == "device_added"

    # The discovery flow for this device should have been aborted
    flows_after = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    device_flows = [
        f
        for f in flows_after
        if f["context"].get("unique_id") == f"bacnet_device_{MOCK_DEVICE_ID}"
    ]
    assert len(device_flows) == 0


async def test_reconfigure_get_interfaces_exception(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_get_local_interfaces: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test reconfigure handles get_local_interfaces exception."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_get_local_interfaces.side_effect = RuntimeError("network error")

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
