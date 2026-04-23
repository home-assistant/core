"""Tests for the Fumis config flow."""

from unittest.mock import MagicMock

from fumis import FumisAuthenticationError, FumisConnectionError, FumisStoveOfflineError
import pytest

from homeassistant.components.fumis.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_fumis")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Clou Duo"
    assert result["data"] == {
        CONF_MAC: "AABBCCDDEEFF",
        CONF_PIN: "1234",
    }
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (FumisAuthenticationError, {CONF_PIN: "invalid_auth"}),
        (FumisStoveOfflineError, {"base": "device_offline"}),
        (FumisConnectionError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    side_effect: type[Exception],
    expected_error: dict[str, str],
) -> None:
    """Test the user flow with errors."""
    mock_fumis.update_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    mock_fumis.update_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "mac_input",
    [
        "aa:bb:cc:dd:ee:ff",
        "AA:BB:CC:DD:EE:FF",
        "aa-bb-cc-dd-ee-ff",
        "aabbccddeeff",
    ],
)
@pytest.mark.usefixtures("mock_fumis")
async def test_user_flow_mac_normalization(
    hass: HomeAssistant,
    mac_input: str,
) -> None:
    """Test the MAC address is normalized regardless of input format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: mac_input,
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "AABBCCDDEEFF"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("mock_fumis")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_fumis")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PIN] == "5678"
    assert mock_config_entry.data[CONF_MAC] == "AABBCCDDEEFF"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (FumisAuthenticationError, {CONF_PIN: "invalid_auth"}),
        (FumisStoveOfflineError, {"base": "device_offline"}),
        (FumisConnectionError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    expected_error: dict[str, str],
) -> None:
    """Test the reauth flow with errors."""
    mock_config_entry.add_to_hass(hass)
    mock_fumis.update_info.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    mock_fumis.update_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_fumis")
async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test DHCP discovery of a Fumis WiRCU module."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.2",
            macaddress="0016d0aabbcc",
            hostname="wircu",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "0016D0AABBCC"
    assert result["data"][CONF_PIN] == "1234"
    assert result["result"].unique_id == "00:16:d0:aa:bb:cc"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (FumisAuthenticationError, {CONF_PIN: "invalid_auth"}),
        (FumisStoveOfflineError, {"base": "device_offline"}),
        (FumisConnectionError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    side_effect: type[Exception],
    expected_error: dict[str, str],
) -> None:
    """Test DHCP discovery with errors."""
    mock_fumis.update_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.2",
            macaddress="0016d0aabbcc",
            hostname="wircu",
        ),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    mock_fumis.update_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_fumis")
async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery = DhcpServiceInfo(
        ip="192.168.1.99",
        macaddress="aabbccddeeff",
        hostname="wircu",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=discovery
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_fumis")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_MAC] == "AABBCCDDEEFF"
    assert mock_config_entry.data[CONF_PIN] == "5678"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (FumisAuthenticationError, {CONF_PIN: "invalid_auth"}),
        (FumisStoveOfflineError, {"base": "device_offline"}),
        (FumisConnectionError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    expected_error: dict[str, str],
) -> None:
    """Test the reconfigure flow with errors."""
    mock_config_entry.add_to_hass(hass)
    mock_fumis.update_info.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    mock_fumis.update_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: "5678"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
