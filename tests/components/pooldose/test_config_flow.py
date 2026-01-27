"""Test the PoolDose config flow."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import RequestStatus

from tests.common import MockConfigEntry, async_fire_time_changed


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
    assert result["data"][CONF_HOST] == "192.168.0.123"
    assert result["data"][CONF_MAC] == "a4e57caabbcc"
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


@pytest.mark.parametrize(
    "api_status",
    [
        RequestStatus.NO_DATA,
        RequestStatus.API_VERSION_UNSUPPORTED,
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


async def test_dhcp_updates_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP discovery updates the host if it has changed."""
    mock_config_entry.add_to_hass(hass)

    # Verify initial host IP
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"

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

    assert mock_config_entry.data[CONF_HOST] == "192.168.0.123"


async def test_dhcp_adds_mac_if_not_present(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP flow adds MAC address if not already in config entry data."""
    # Create a config entry without MAC address
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TEST123456789",
        data={CONF_HOST: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    # Verify initial state has no MAC
    assert CONF_MAC not in entry.data

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

    # Verify MAC was added to the config entry
    assert entry.data[CONF_HOST] == "192.168.0.123"
    assert entry.data[CONF_MAC] == "a4e57caabbcc"


async def test_dhcp_preserves_existing_mac(
    hass: HomeAssistant, mock_pooldose_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test that DHCP flow preserves existing MAC in config entry data."""
    # Create a config entry with MAC address already set
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TEST123456789",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_MAC: "existing11aabb",  # Existing MAC that should be preserved
        },
    )
    entry.add_to_hass(hass)

    # Verify initial state has the expected MAC
    assert entry.data[CONF_MAC] == "existing11aabb"

    # Simulate DHCP discovery event with different MAC
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.0.123", hostname="kommspot", macaddress="different22ccdd"
        ),
    )

    # Verify flow aborts as device is already configured
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify MAC in config entry was NOT updated (original MAC preserved)
    assert entry.data[CONF_HOST] == "192.168.0.123"  # IP was updated
    assert entry.data[CONF_MAC] == "existing11aabb"  # MAC remains unchanged
    assert entry.data[CONF_MAC] != "different22ccdd"  # Not updated to new MAC


async def _start_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, host_ip: str
) -> Any:
    """Initialize a reconfigure flow for PoolDose and submit new host."""
    mock_config_entry.add_to_hass(hass)

    reconfigure_result = await mock_config_entry.start_reconfigure_flow(hass)

    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"

    return await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"], {CONF_HOST: host_ip}
    )


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful reconfigure updates host and reloads entry."""
    # Ensure the mocked device returns the same serial number as the
    # config entry so the reconfigure flow matches the device
    mock_pooldose_client.device_info = {"SERIAL_NUMBER": mock_config_entry.unique_id}

    result = await _start_reconfigure_flow(hass, mock_config_entry, "192.168.0.200")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Config entry should have updated host
    assert mock_config_entry.data.get(CONF_HOST) == "192.168.0.200"

    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Config entry should have updated host
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert entry.data.get(CONF_HOST) == "192.168.0.200"


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure shows cannot_connect when device unreachable."""
    mock_pooldose_client.connect.return_value = RequestStatus.HOST_UNREACHABLE

    result = await _start_reconfigure_flow(hass, mock_config_entry, "192.168.0.200")

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_wrong_device(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when serial number doesn't match existing entry."""
    # Return device info with different serial number
    mock_pooldose_client.device_info = {"SERIAL_NUMBER": "OTHER123"}

    result = await _start_reconfigure_flow(hass, mock_config_entry, "192.168.0.200")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
