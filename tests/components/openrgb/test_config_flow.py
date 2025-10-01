"""Tests for the OpenRGB config flow."""

from unittest.mock import MagicMock, patch

from openrgb.utils import OpenRGBDisconnected, SDKVersionError
import pytest

from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
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
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenRGB (aa:bb:cc:dd:ee:ff)"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6742,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_get_mac_address: MagicMock
) -> None:
    """Test user flow when cannot connect to OpenRGB SDK Server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=ConnectionRefusedError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_openrgb_disconnected(
    hass: HomeAssistant, mock_get_mac_address: MagicMock
) -> None:
    """Test user flow when OpenRGB disconnects."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=OpenRGBDisconnected,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_sdk_version_error(
    hass: HomeAssistant, mock_get_mac_address: MagicMock
) -> None:
    """Test user flow with SDK version mismatch."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=SDKVersionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_unable_to_determine_mac(hass: HomeAssistant) -> None:
    """Test user flow when unable to determine MAC address (should still work)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.get_mac_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
        )

    # Should succeed without MAC address
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenRGB (127.0.0.1:6742)"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 6742,
    }
    assert result["result"].unique_id == "127.0.0.1:6742"


@pytest.mark.usefixtures(
    "mock_setup_entry", "mock_openrgb_client", "mock_get_mac_address"
)
async def test_user_flow_ipv6(hass: HomeAssistant) -> None:
    """Test user flow with IPv6 address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "::1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenRGB (aa:bb:cc:dd:ee:ff)"
    assert result["data"] == {
        CONF_HOST: "::1",
        CONF_PORT: 6742,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_get_mac_address: MagicMock
) -> None:
    """Test user flow with unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=RuntimeError("Test error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


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
        user_input={CONF_HOST: "127.0.0.1", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_openrgb_client", "mock_get_mac_address")
async def test_dhcp_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test DHCP flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

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
    assert result["reason"] == "already_configured"

    # Verify that the host was updated
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"


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
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100", CONF_PORT: 6742},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify that the host was updated
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow when cannot connect."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=ConnectionRefusedError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry", "mock_openrgb_client")
async def test_reconfigure_flow_unknown_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with unknown error."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.openrgb.config_flow.OpenRGBClient",
        side_effect=RuntimeError("Test error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100", CONF_PORT: 6742},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unknown"}
