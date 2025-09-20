from unittest.mock import patch, AsyncMock
from ipaddress import ip_address

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.components.solarman.const import DOMAIN
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, load_json_object_fixture

# Configure test constants
TEST_HOST = "192.168.1.100"
TEST_PORT = 8080
TEST_SCAN_INTERVAL = 30
TEST_DEVICE_SN = "SN1234567890"
TEST_FW_VERSION = "LSW3_01_E030_SS_00_00.00.00.03"
TEST_MODEL = "SP-2W-EU"


async def test_flow_success(hass: HomeAssistant):
    """Test successful configuration flow."""

    # Initiate config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Verify initial form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Mock get_config returning success.
    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        return_value=load_json_object_fixture("P1-2W/config.json", DOMAIN)
    ):
        # Submit valid data
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT, "scan_interval": TEST_SCAN_INTERVAL},
        )

    # Verify entry creation
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{"P1-2W"} ({TEST_HOST})"

    # Verify configuration data.
    data = result["data"]
    assert data["host"] == TEST_HOST
    assert data["port"] == TEST_PORT
    assert data["scan_interval"] == TEST_SCAN_INTERVAL
    assert data["sn"] == TEST_DEVICE_SN
    assert data["fw_version"] == TEST_FW_VERSION
    assert data["model"] == "P1-2W"

@pytest.mark.parametrize(
    "exception, expected_error",
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ]
)
async def test_flow_error(
    hass: HomeAssistant, 
    exception: Exception,
    expected_error: str
):
    """Test connection error handling."""
    # Initiate and submit config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock get_config raising connection error
    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        # Submit config flow
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT, "scan_interval": TEST_SCAN_INTERVAL},
        )

    # Verify error form display.
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Test duplicate entry handling."""
    # Create existing config entry.
    mock_config_entry.add_to_hass(hass)

    # Mock get_config returning same device
    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        return_value=load_json_object_fixture("SP-2W-EU/config.json", DOMAIN)
    ):
        # Initiate and submit config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": TEST_HOST, "port": TEST_PORT}
        )

    # Verify flow abort
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_reconfigure_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert mock_config_entry.data["host"] == TEST_HOST

    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        return_value=load_json_object_fixture("SP-2W-EU/config.json", DOMAIN)
    ):
        # Submit valid data
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.10", "port": TEST_PORT, "scan_interval": TEST_SCAN_INTERVAL},
        )


    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # changed entry
    assert mock_config_entry.data["host"] == "192.168.1.10"


@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_reconfigure_another_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert mock_config_entry.data["host"] == TEST_HOST

    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        return_value=load_json_object_fixture("P1-2W/config.json", DOMAIN)
    ):
        # Submit valid data
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "192.168.1.10", "port": TEST_PORT, "scan_interval": TEST_SCAN_INTERVAL},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"


@pytest.mark.parametrize(
    "exception, expected_error",
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_reconfigure_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: str
) -> None:
    """Test reconfiguration."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        side_effect=exception,
    ):
        # Submit config flow
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT, "scan_interval": TEST_SCAN_INTERVAL},
        )
        
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    with patch(
        "homeassistant.components.solarman.config_flow.get_config",
        new_callable=AsyncMock,
        return_value=load_json_object_fixture("SP-2W-EU/config.json", DOMAIN)
    ):
        # Submit valid data
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": TEST_HOST, "port": TEST_PORT, "scan_interval": TEST_SCAN_INTERVAL},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_zeroconf(hass: HomeAssistant, mock_solarman: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_http._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
                "fw_version": TEST_FW_VERSION
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], 
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_MODEL} ({TEST_HOST})"

    data = result["data"]
    assert data["host"] == TEST_HOST
    assert data["port"] == TEST_PORT
    assert data["scan_interval"] == TEST_SCAN_INTERVAL
    assert data["sn"] == TEST_DEVICE_SN
    assert data["fw_version"] == TEST_FW_VERSION
    assert data["model"] == TEST_MODEL

@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_zeroconf_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solarman: AsyncMock,
) -> None:
    """Test zeroconf discovery when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_http._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
                "fw_version": TEST_FW_VERSION
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

@pytest.mark.parametrize(
    "device_fixture", ["SP-2W-EU"], indirect=True
)
async def test_zeroconf_ip_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discovery setup updates new config data."""
    mock_config_entry.add_to_hass(hass)

    # preflight check, see if the ip address is already in use
    assert mock_config_entry.data["host"] == TEST_HOST

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.101"),
            ip_addresses=[ip_address("192.168.1.101")],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_http._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
                "fw_version": TEST_FW_VERSION
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data["host"] == "192.168.1.101"