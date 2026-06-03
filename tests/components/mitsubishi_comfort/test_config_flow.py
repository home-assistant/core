"""Tests for the Mitsubishi Comfort config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.mitsubishi_comfort.const import CONF_ADDRESSES, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_MAC

from tests.common import MockConfigEntry

MOCK_USERNAME = "test@test.com"
MOCK_PASSWORD = "testpass"


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry and async_unload_entry."""
    with (
        patch(
            "homeassistant.components.mitsubishi_comfort.async_setup_entry",
            return_value=True,
        ) as mock,
        patch(
            "homeassistant.components.mitsubishi_comfort.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock


async def test_user_step_success(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow shows form then creates entry."""
    # First call with no input shows form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit credentials creates entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Mitsubishi Comfort ({MOCK_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "discover_return", "expected_error"),
    [
        (AuthenticationError("bad creds"), None, "invalid_auth"),
        (DeviceConnectionError("nope"), None, "cannot_connect"),
        (RuntimeError("Unexpected"), None, "unknown"),
        (None, {}, "no_devices"),
    ],
    ids=["invalid_auth", "cannot_connect", "unknown_error", "no_devices"],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_cloud_account: AsyncMock,
    side_effect: Exception | None,
    discover_return: dict | None,
    expected_error: str,
) -> None:
    """Test config flow error handling."""
    if side_effect:
        mock_cloud_account.login.side_effect = side_effect
    elif discover_return is not None:
        mock_cloud_account.discover_devices.return_value = discover_return

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_account: AsyncMock,
) -> None:
    """Test that duplicate config is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _dhcp_info(ip: str, mac: str = MOCK_MAC) -> DhcpServiceInfo:
    """Build DHCP discovery info (DHCP reports MACs without separators)."""
    return DhcpServiceInfo(
        ip=ip, hostname="kumo", macaddress=mac.replace(":", "").lower()
    )


async def test_dhcp_updates_address_and_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery records a new IP for a known device and reloads."""
    mock_config_entry.add_to_hass(hass)
    formatted_mac = format_mac(MOCK_MAC)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.250"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_ADDRESSES][formatted_mac] == "192.168.1.250"
    mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_dhcp_same_address_does_not_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery of an unchanged IP does not trigger a reload."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.100"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_reload.assert_not_called()


async def test_dhcp_unknown_device_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery of a MAC not owned by any entry changes nothing."""
    mock_config_entry.add_to_hass(hass)
    original = dict(mock_config_entry.data[CONF_ADDRESSES])

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_schedule_reload"
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=_dhcp_info("192.168.1.251", mac="99:99:99:99:99:99"),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_ADDRESSES] == original
    mock_reload.assert_not_called()


async def test_dhcp_no_account_aborts(hass: HomeAssistant) -> None:
    """Test DHCP discovery with no configured account aborts without a flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=_dhcp_info("192.168.1.252"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
