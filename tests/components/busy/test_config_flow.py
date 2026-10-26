"""Test BUSY Bar pairing."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from busylib import types
from busylib.exceptions import BusyBarAPIError, BusyBarRequestError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DEVICE_ID, HOST

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def discovery(host: str = HOST, name: str = "Office") -> ZeroconfServiceInfo:
    """Build a BUSY Bar announcement."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        port=80,
        hostname=f"busybar-{DEVICE_ID}.local.",
        type="_http._tcp.local.",
        name=f"busybar-{DEVICE_ID}._http._tcp.local.",
        properties={"name": name},
    )


async def start_user(hass: HomeAssistant) -> ConfigFlowResult:
    """Submit the manual address form."""
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )


async def test_manual(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Pair a manually addressed bar."""
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": HOST, "token": "12345678-token"}
    assert result["title"] == "BUSY Bar"
    assert result["result"].unique_id == DEVICE_ID
    mock_client.access_token_mint.assert_awaited_once()


async def test_zeroconf(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Confirm a discovered bar before pairing."""
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_ZEROCONF}, data=discovery()
    )
    assert result["step_id"] == "zeroconf_confirm"
    mock_client.access_token_mint.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID
    assert result["title"] == "Office"


async def test_key_retry(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Reject an incorrect API key and accept a corrected one."""
    mock_client.access.return_value = types.HttpAccessInfo(mode="key")
    result = await start_user(hass)
    assert result["step_id"] == "key"
    mock_client.access_token_mint.assert_not_awaited()
    mock_client.status_device.side_effect = BusyBarAPIError("invalid", status_code=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    mock_client.access_token_mint.assert_not_awaited()
    mock_client.status_device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "correct"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_disabled(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Abort when the HTTP API is disabled."""
    mock_client.access.return_value = types.HttpAccessInfo(mode="disabled")
    result = await start_user(hass)
    assert result["reason"] == "http_api_disabled"
    mock_client.access_token_mint.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "error", "expected"),
    [
        ("access", BusyBarRequestError("offline"), "cannot_connect"),
        ("status_device", BusyBarRequestError("offline"), "cannot_connect"),
        ("access_token_mint", BusyBarRequestError("offline"), "cannot_connect"),
        (
            "access_token_mint",
            BusyBarAPIError("server", status_code=500),
            "cannot_connect",
        ),
        (
            "access_token_mint",
            BusyBarAPIError("invalid", status_code=403),
            "invalid_auth",
        ),
        ("access", ValueError("invalid response"), "cannot_connect"),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    method: str,
    error: Exception,
    expected: str,
) -> None:
    """Recover from pairing errors after correcting the address."""
    getattr(mock_client, method).side_effect = error
    result = await start_user(hass)
    assert result["errors"] == {"base": expected}
    getattr(mock_client, method).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_retry(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Retry discovery confirmation after a connection failure."""
    mock_client.access.side_effect = BusyBarRequestError("offline")
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_ZEROCONF}, data=discovery(name="")
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "cannot_connect"}
    mock_client.access.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BUSY Bar"


async def test_manual_duplicate(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reject repeated setup before issuing another token."""
    mock_config_entry.add_to_hass(hass)
    for _ in range(2):
        result = await start_user(hass)
        assert result["reason"] == "already_configured"
    mock_client.access_token_mint.assert_not_awaited()


async def test_discovery_updates_host(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Update the address of a configured bar."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_ZEROCONF}, data=discovery("192.168.50.21")
    )
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data["host"] == "192.168.50.21"
    mock_client.access.assert_not_awaited()


async def test_manual_host_change(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Allow a different bar after a failed pairing attempt."""
    mock_client.access_token_mint.side_effect = BusyBarRequestError("offline")
    result = await start_user(hass)
    assert result["errors"] == {"base": "cannot_connect"}
    mock_client.access_token_mint.side_effect = None
    mock_client.status_device.return_value = types.StatusDevice(
        usb_mac="00:11:22:33:44:55"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "192.168.50.21"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "001122334455"
    assert result["data"]["host"] == "192.168.50.21"
