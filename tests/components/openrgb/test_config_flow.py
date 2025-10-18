"""Tests for the OpenRGB config flow."""

import socket

from openrgb.utils import OpenRGBDisconnected, SDKVersionError
import pytest

from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "mock_setup_entry", "mock_openrgb_client", "mock_get_mac_address"
)
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Test Computer",
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6742,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Computer"
    assert result["data"] == {
        CONF_NAME: "Test Computer",
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6742,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (ConnectionRefusedError, "cannot_connect"),
        (OpenRGBDisconnected, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (socket.gaierror, "cannot_connect"),
        (SDKVersionError, "cannot_connect"),
        (RuntimeError("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_get_mac_address")
async def test_user_flow_errors(
    hass: HomeAssistant, exception: Exception, error_key: str, mock_openrgb_client
) -> None:
    """Test user flow with various errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_openrgb_client.client_class_mock.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Test Server", CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_key}

    # Test recovery from error
    mock_openrgb_client.client_class_mock.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Test Server", CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Server"
    assert result["data"] == {
        CONF_NAME: "Test Server",
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6742,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }


@pytest.mark.usefixtures(
    "mock_setup_entry", "mock_openrgb_client", "mock_get_mac_address"
)
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Test Server", CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow when trying to add duplicate host/port combination."""
    mock_config_entry.add_to_hass(hass)

    # Create another config entry with different host/port
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other Computer",
        data={
            CONF_NAME: "Other Computer",
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 6743,
        },
        entry_id="01J0EXAMPLE0CONFIGENTRY01",
    )
    other_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    # Try to add entry with same host/port as other_entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Yet Another Computer",
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 6743,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_openrgb_client", "mock_get_mac_address")
async def test_dhcp_flow_not_configured(hass: HomeAssistant) -> None:
    """Test DHCP flow when device is not configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="aabbccddeeff",
            hostname="openrgb",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures(
    "mock_setup_entry", "mock_openrgb_client", "mock_get_mac_address"
)
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 6743,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"
    assert mock_config_entry.data[CONF_PORT] == 6743


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (ConnectionRefusedError, "cannot_connect"),
        (OpenRGBDisconnected, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (socket.gaierror, "cannot_connect"),
        (SDKVersionError, "cannot_connect"),
        (RuntimeError("Test error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_get_mac_address")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error_key: str,
    mock_openrgb_client,
) -> None:
    """Test reconfiguration flow with various errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_openrgb_client.client_class_mock.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100", CONF_PORT: 6743},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error_key}

    # Test recovery from error
    mock_openrgb_client.client_class_mock.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100", CONF_PORT: 6743},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"
    assert mock_config_entry.data[CONF_PORT] == 6743


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_reconfigure_flow_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguration flow when new config matches another existing entry."""
    mock_config_entry.add_to_hass(hass)

    # Create another config entry with different host/port
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other Computer",
        data={
            CONF_NAME: "Other Computer",
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 6743,
        },
        entry_id="01J0EXAMPLE0CONFIGENTRY01",
    )
    other_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    # Try to reconfigure to match the other entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 6743,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
