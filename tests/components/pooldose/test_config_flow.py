"""Test the PoolDose config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import RequestStatus

from tests.common import MockConfigEntry


async def test_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PoolDose TEST123456789"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}
    assert result["result"].unique_id == "TEST123456789"


async def test_device_unreachable(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the form shows error when device is unreachable."""
    mock_pooldose_client.is_connected = False
    mock_pooldose_client.connect.return_value = RequestStatus.HOST_UNREACHABLE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_pooldose_client.is_connected = True
    mock_pooldose_client.connect.return_value = RequestStatus.SUCCESS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_api_version_unsupported(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the form shows error when API version is unsupported."""
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        {"api_version_is": "v0.9", "api_version_should": "v1.0"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_supported"}

    mock_pooldose_client.is_connected = True
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.SUCCESS,
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_no_device_info(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    device_info: dict[str, Any],
) -> None:
    """Test that the form shows error when device_info is None."""
    mock_pooldose_client.device_info = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_device_info"}

    mock_pooldose_client.device_info = device_info

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("client_status", "expected_error"),
    [
        (RequestStatus.HOST_UNREACHABLE, "cannot_connect"),
        (RequestStatus.PARAMS_FETCH_FAILED, "params_fetch_failed"),
        (RequestStatus.UNKNOWN_ERROR, "cannot_connect"),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    client_status: str,
    expected_error: str,
) -> None:
    """Test that the form shows appropriate errors for various connection issues."""
    mock_pooldose_client.connect.return_value = client_status

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_pooldose_client.connect.return_value = RequestStatus.SUCCESS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_api_no_data(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the form shows error when API returns NO_DATA."""
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.NO_DATA,
        {},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_set"}

    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.SUCCESS,
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_no_serial_number(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    device_info: dict[str, Any],
) -> None:
    """Test that the form shows error when device_info has no serial number."""
    mock_pooldose_client.device_info = {"NAME": "Pool Device", "MODEL": "POOL DOSE"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_serial_number"}

    mock_pooldose_client.device_info = device_info

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the flow aborts if the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full DHCP config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PoolDose TEST123456789"
    assert result["data"] == {CONF_HOST: "192.168.0.123"}
    assert result["result"].unique_id == "TEST123456789"


async def test_dhcp_no_serial_number(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that the DHCP flow aborts if no serial number is found."""
    mock_pooldose_client.device_info = {"NAME": "Pool Device", "MODEL": "POOL DOSE"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"


@pytest.mark.parametrize(
    ("client_status"),
    [
        (RequestStatus.HOST_UNREACHABLE),
        (RequestStatus.PARAMS_FETCH_FAILED),
        (RequestStatus.UNKNOWN_ERROR),
    ],
)
async def test_dhcp_connection_errors(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    client_status: str,
) -> None:
    """Test that the DHCP flow aborts on connection errors."""
    mock_pooldose_client.connect.return_value = client_status

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"

    # Reset for other tests
    mock_pooldose_client.connect.return_value = RequestStatus.SUCCESS


@pytest.mark.parametrize(
    ("api_status"),
    [
        (RequestStatus.NO_DATA),
        (RequestStatus.API_VERSION_UNSUPPORTED),
    ],
)
async def test_dhcp_api_errors(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    api_status: str,
) -> None:
    """Test that the DHCP flow aborts on API errors."""
    mock_pooldose_client.check_apiversion_supported.return_value = (api_status, {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"

    # Reset for other tests
    mock_pooldose_client.check_apiversion_supported.return_value = (
        RequestStatus.SUCCESS,
        {},
    )


async def test_dhcp_adds_mac_connection(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP flow adds MAC address as connection to device registry."""
    # Create a config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TEST123456789",
        data={CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    # Create device in registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "TEST123456789")},
        name="PoolDose TEST123456789",
        manufacturer="Seko",
        model="POOL DOSE",
    )
    assert device is not None

    # Verify initial state has no MAC connection
    mac_conn = ("network_mac", "a4e57caabbcc")
    assert mac_conn not in device.connections

    # Simulate DHCP discovery event
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )

    # Verify flow aborts as device is already configured
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify MAC address was added to device registry
    device = device_registry.async_get_device(identifiers={(DOMAIN, "TEST123456789")})
    assert device is not None
    assert mac_conn in device.connections

    # Verify host was updated in config entry
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_HOST] == "192.168.0.123"


async def test_dhcp_mac_connection_not_duplicated(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP flow does not add duplicate MAC connections."""
    # Create and load a config entry with MAC connection already in device registry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TEST123456789",
        data={CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    # Create device in registry
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "TEST123456789")},
        name="PoolDose TEST123456789",
        manufacturer="Seko",
        model="POOL DOSE",
    )
    assert device is not None

    # Setup entry and add MAC connection
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device_registry.async_update_device(
        device.id, new_connections={("network_mac", "a4e57caabbcc")}
    )

    # Verify initial state has MAC connection
    device = device_registry.async_get_device(identifiers={(DOMAIN, "TEST123456789")})
    assert ("network_mac", "a4e57caabbcc") in device.connections
    connection_count = len(device.connections)

    # Simulate DHCP discovery event with same MAC
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )

    # Verify flow aborts as device is already configured
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify no duplicate MAC connection was added (connections are still the same)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "TEST123456789")})
    assert len(device.connections) == connection_count


async def test_dhcp_updates_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP discovery updates the host if it has changed."""
    # Create and load a config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TEST123456789",
        data={CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    # Create device in registry to match the implementation
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "TEST123456789")},
        name="PoolDose TEST123456789",
        manufacturer="Seko",
        model="POOL DOSE",
    )
    assert device is not None

    # Verify initial host IP
    assert entry.data[CONF_HOST] == "192.168.1.100"

    # Simulate DHCP discovery event with different IP
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )

    # Verify flow aborts as device is already configured
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify host was updated in the config entry
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.0.123"

    # Verify MAC was added as a connection
    device = device_registry.async_get_device(identifiers={(DOMAIN, "TEST123456789")})
    assert device is not None
    assert ("network_mac", "a4e57caabbcc") in device.connections


async def test_duplicate_dhcp_entries_not_allowed(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the same device cannot be configured twice via DHCP."""
    # First DHCP discovery creates a config entry
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "dhcp_confirm"

    # Complete the first flow
    result2 = await hass.config_entries.flow.async_configure(result1["flow_id"], {})
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "PoolDose TEST123456789"

    # Try to set up the same device again with different IP
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.124", hostname="kommspot", macaddress="a4e57caabbcc"
        ),
    )
    # Flow should abort as the device is already configured
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"

    # Verify the host was updated in the config entry
    entry = hass.config_entries.async_get_entry(result2["result"].entry_id)
    assert entry.data[CONF_HOST] == "192.168.0.124"
