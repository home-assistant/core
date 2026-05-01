"""Tests the Indevolt config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant.components.indevolt.const import (
    CONF_GENERATION,
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import ALT_TEST_HOST, TEST_DEVICE_SN_GEN2, TEST_HOST, TEST_MODEL_GEN2

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user-initiated config flow."""

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Verify correct form is returned
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test config entry creation (with success)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": TEST_HOST}
    )

    # Verify entry is created with correct data
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"INDEVOLT {TEST_MODEL_GEN2}"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_SERIAL_NUMBER: TEST_DEVICE_SN_GEN2,
        CONF_MODEL: TEST_MODEL_GEN2,
        CONF_GENERATION: 2,
    }
    assert result["result"].unique_id == TEST_DEVICE_SN_GEN2


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors in user flow."""

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify exception is thrown with correct error message
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery by patching the library to work
    mock_indevolt.get_config.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify entry is created with correct data
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"INDEVOLT {TEST_MODEL_GEN2}"


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test duplicate entry aborts the flow."""
    mock_config_entry.add_to_hass(hass)

    # Initiate user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Test duplicate entry creation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify flow is aborted with correct reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)

    # Initiate reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    # Verify correct form is returned
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: ALT_TEST_HOST}
    )

    # Verify flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Flush pending tasks
    await hass.async_block_till_done()

    # Verify entry is updated
    assert mock_config_entry.data[CONF_HOST] == ALT_TEST_HOST
    assert mock_config_entry.data[CONF_SERIAL_NUMBER] == TEST_DEVICE_SN_GEN2


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors in reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    # Initiate reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    # Configure mock to raise exception
    mock_indevolt.get_config.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify exception is thrown with correct error message
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Test recovery by patching the library to work
    mock_indevolt.get_config.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify entry is created with correct data and flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Flush pending tasks
    await hass.async_block_till_done()


async def test_reconfigure_flow_different_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_indevolt: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure aborts when connecting to a different device."""
    mock_config_entry.add_to_hass(hass)

    # Setup new device for configuration
    mock_indevolt.get_config.return_value = {
        "device": {
            "sn": "DIFFERENT-SERIAL-99999999",
            "type": "CMS-OTHER",
            "generation": 1,
            "fw": "1.0.0",
        }
    }

    # Initiate reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    # Configure mock to cause host collision with different device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: ALT_TEST_HOST}
    )

    # Verify flow is aborted with correct reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_device"

    # Flush pending tasks
    await hass.async_block_till_done()


async def test_dhcp_flow_success(
    hass: HomeAssistant, mock_indevolt: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful discovery flow."""
    # Verify confirmation form is returned with correct device info
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip=TEST_HOST,
            hostname="indevolt",
            macaddress="1c784b8d47bb",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"][CONF_HOST] == TEST_HOST
    assert result["description_placeholders"][CONF_MODEL] == TEST_MODEL_GEN2

    # Verify entry is created with correct data
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"INDEVOLT {TEST_MODEL_GEN2}"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_SERIAL_NUMBER: TEST_DEVICE_SN_GEN2,
        CONF_MODEL: TEST_MODEL_GEN2,
        CONF_GENERATION: 2,
    }
    assert result["result"].unique_id == TEST_DEVICE_SN_GEN2


async def test_dhcp_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test DHCP discovery aborts if already configured."""
    mock_config_entry.add_to_hass(hass)

    # Verify flow is aborted if device is already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip=TEST_HOST,
            hostname="indevolt",
            macaddress="1c784b8d47bb",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_ip_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_indevolt: AsyncMock
) -> None:
    """Test DHCP discovery updates config entry host if the device moved to a new IP."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST

    # Verify flow is aborted on ip change and existing entry host is updated
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip=ALT_TEST_HOST,
            hostname="indevolt",
            macaddress="1c784b8d47bb",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == ALT_TEST_HOST


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (TimeoutError, "cannot_connect"),
        (ConnectionError, "cannot_connect"),
        (ClientError, "cannot_connect"),
    ],
)
async def test_dhcp_cannot_connect(
    hass: HomeAssistant,
    mock_indevolt: AsyncMock,
    exception: type[Exception],
    reason: str,
) -> None:
    """Test discovery aborts on connection errors."""

    # Initiate discovery flow with exception
    mock_indevolt.get_config.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip=TEST_HOST,
            hostname="indevolt",
            macaddress="1c784b8d47bb",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
