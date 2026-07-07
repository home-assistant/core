"""Test the Solarman config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.solarman.const import CONF_SN, DOMAIN, MODEL_NAME_MAP
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

# Configure test constants
TEST_HOST = "192.168.1.100"
TEST_DEVICE_SN = "SN1234567890"
TEST_MODEL = "SP-2W-EU"


@pytest.mark.parametrize("device_fixture", ["P1-2W"], indirect=True)
async def test_flow_success(hass: HomeAssistant, mock_solarman: AsyncMock) -> None:
    """Test successful configuration flow."""

    # Initiate config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Verify initial form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit valid data
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify entry creation
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"P1 Meter Reader ({TEST_HOST})"
    assert result["context"]["unique_id"] == "SN2345678901"

    # Verify configuration data.
    data = result["data"]
    assert data[CONF_HOST] == TEST_HOST
    assert data[CONF_SN] == "SN2345678901"
    assert data[CONF_MODEL] == "P1-2W"


@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
async def test_flow_error(
    hass: HomeAssistant,
    mock_solarman: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection error handling."""
    # Initiate and submit config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_solarman.get_config.side_effect = exception

    # Submit config flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    # Verify error form display.
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    mock_solarman.get_config.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_solarman: AsyncMock
) -> None:
    """Test duplicate entry handling."""
    # Create existing config entry.
    mock_config_entry.add_to_hass(hass)

    # Initiate and submit config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    # Verify flow abort
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_zeroconf(hass: HomeAssistant, mock_solarman: AsyncMock) -> None:
    """Test zeroconf discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_solarman._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{MODEL_NAME_MAP[TEST_MODEL]} ({TEST_HOST})"

    data = result["data"]
    assert data[CONF_HOST] == TEST_HOST
    assert data[CONF_SN] == TEST_DEVICE_SN
    assert data[CONF_MODEL] == TEST_MODEL
    assert result["context"]["unique_id"] == TEST_DEVICE_SN


@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_zeroconf_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solarman: AsyncMock,
) -> None:
    """Test zeroconf discovery when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_solarman._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_zeroconf_ip_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_solarman: AsyncMock
) -> None:
    """Test discovery setup updates new config data."""
    mock_config_entry.add_to_hass(hass)

    # preflight check, see if the ip address is already in use
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.101"),
            ip_addresses=[ip_address("192.168.1.101")],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_solarman._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (TimeoutError, "timeout"),
        (ConnectionError, "cannot_connect"),
        (Exception("Some unknown error"), "unknown"),
    ],
)
@pytest.mark.parametrize("device_fixture", ["SP-2W-EU"], indirect=True)
async def test_zeroconf_error(
    hass: HomeAssistant,
    mock_solarman: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test discovery setup."""
    mock_solarman.get_config.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address(TEST_HOST),
            ip_addresses=[ip_address(TEST_HOST)],
            name="mock_name",
            port=8080,
            hostname="mock_hostname",
            type="_solarman._tcp.local.",
            properties={
                "product_type": "SP-2W-EU",
                "serial": TEST_DEVICE_SN,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error
