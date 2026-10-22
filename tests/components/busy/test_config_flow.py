"""Test manual and discovered pairing."""

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


def discovery(host: str = HOST, name: str | None = "Office") -> ZeroconfServiceInfo:
    """Build a standard HTTP announcement from the bar.

    Include the stable service name and the currently announced address.
    """
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        port=80,
        hostname=f"busybar-{DEVICE_ID}.local.",
        type="_http._tcp.local.",
        name=f"busybar-{DEVICE_ID}._http._tcp.local.",
        properties={"name": name} if name else {},
    )


async def start_user(hass: HomeAssistant) -> ConfigFlowResult:
    """Submit a manual address through the user form.

    Start without input before configuring the flow as the frontend does.
    """
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_ZEROCONF])
async def test_pair(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    source: str,
) -> None:
    """Confirm manual and discovered pairing share one stable identity.

    Exercise both entry points and verify the resulting token and unique ID.
    """
    result = await hass.config_entries.flow.async_init(
        "busy",
        context={"source": source},
        data={SOURCE_USER: None, SOURCE_ZEROCONF: discovery()}[source],
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {SOURCE_USER: {"host": HOST}, SOURCE_ZEROCONF: {}}[source]
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": HOST, "token": "token"}
    assert result["result"].unique_id == DEVICE_ID
    mock_client.access_token_mint.assert_awaited_once()
    assert mock_client.__aexit__.await_count == 2


async def test_key_retry(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Request a key, reject a wrong one and accept a corrected key.

    Keep the flow active through a refusal and a successful retry.
    """
    mock_client.access.return_value = types.HttpAccessInfo(mode="key")
    result = await start_user(hass)
    assert result["step_id"] == "key"
    mock_client.access_token_mint.assert_not_called()
    mock_client.access_token_mint.side_effect = BusyBarAPIError(
        "invalid", status_code=401
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
    mock_client.access_token_mint.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"password": "correct"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_disabled(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Abort from the access mode without trying to mint a token.

    Check that disabled access prevents token issuance.
    """
    mock_client.access.return_value = types.HttpAccessInfo(mode="disabled")
    result = await start_user(hass)
    assert result["reason"] == "http_api_disabled"
    mock_client.access_token_mint.assert_not_called()


@pytest.mark.parametrize(
    ("method", "error", "expected"),
    [
        ("access", BusyBarRequestError("offline"), "cannot_connect"),
        ("access_token_mint", BusyBarRequestError("offline"), "cannot_connect"),
        ("status_device", BusyBarRequestError("offline"), "cannot_connect"),
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
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    method: str,
    error: Exception,
    expected: str,
) -> None:
    """Keep connectivity failures separate from authentication refusals.

    Inject failures at each request boundary and inspect the form error.
    """
    getattr(mock_client, method).side_effect = error
    result = await start_user(hass)
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected}
    getattr(mock_client, method).side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("token", [None, "token"])
async def test_incomplete_pairing(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    token: str | None,
) -> None:
    """Reject incomplete pairing responses.

    Require both a token and the USB MAC used by discovery.
    """
    mock_client.access_token_mint.return_value.token = token
    mock_client.status_device.return_value = types.StatusDevice()
    result = await start_user(hass)
    assert result["reason"] == "cannot_connect"


async def test_manual_duplicate(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Prevent manually pairing an already configured bar.

    Keep the existing entry when the same identity is added again.
    """
    mock_config_entry.add_to_hass(hass)
    result = await start_user(hass)
    assert result["reason"] == "already_configured"


async def test_discovery_updates_host(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Update a configured bar when its DHCP address changes.

    Preserve the token and avoid pairing the same device twice.
    """
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_ZEROCONF}, data=discovery("192.168.50.21")
    )
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data["host"] == "192.168.50.21"
    mock_client.access.assert_not_called()


async def test_discovered_identity_mismatch(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Reject a different device now answering at the discovered address.

    Compare the API identity with the original discovery.
    """
    mock_client.status_device.return_value = types.StatusDevice(
        usb_mac="00:11:22:33:44:55"
    )
    result = await hass.config_entries.flow.async_init(
        "busy", context={"source": SOURCE_ZEROCONF}, data=discovery(name=None)
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "wrong_device"
