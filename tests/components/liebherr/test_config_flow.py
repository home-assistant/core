"""Test the liebherr config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

MOCK_API_KEY = "test-api-key"
MOCK_USER_INPUT = {CONF_API_KEY: MOCK_API_KEY}

MOCK_ZEROCONF_SERVICE_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.100"),
    ip_addresses=[ip_address("192.168.1.100")],
    port=80,
    hostname="liebherr-device.local.",
    type="_http._tcp.local.",
    name="liebherr-fridge._http._tcp.local.",
    properties={},
)


async def _start_flow(hass: HomeAssistant) -> ConfigFlowResult:
    """Start a config flow and return the initial result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {}
    return result


async def _complete_flow_successfully(
    hass: HomeAssistant,
    flow_id: str,
    mock_setup_entry: AsyncMock,
) -> ConfigFlowResult:
    """Complete a flow successfully and verify the result."""
    result = await hass.config_entries.flow.async_configure(flow_id, MOCK_USER_INPUT)
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Liebherr"
    assert result.get("data") == MOCK_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1
    return result


async def test_form(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test we get the form."""
    result = await _start_flow(hass)
    assert result == snapshot

    result = await _complete_flow_successfully(
        hass, result.get("flow_id"), mock_setup_entry
    )
    assert result == snapshot


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (LiebherrAuthenticationError("Invalid"), "invalid_auth"),
        (LiebherrConnectionError("Failed"), "cannot_connect"),
        (Exception("Unexpected"), "unknown"),
    ],
)
async def test_form_errors_with_recovery(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test error handling with successful recovery."""
    result = await _start_flow(hass)

    # Trigger error
    mock_liebherr_client.get_devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"), MOCK_USER_INPUT
    )
    assert result == snapshot

    # Recover and complete successfully
    mock_liebherr_client.get_devices.side_effect = None
    result = await _complete_flow_successfully(
        hass, result.get("flow_id"), mock_setup_entry
    )
    assert result == snapshot


async def test_form_no_devices(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test we handle no devices found."""
    result = await _start_flow(hass)

    mock_liebherr_client.get_devices.return_value = []
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"), MOCK_USER_INPUT
    )
    assert result == snapshot


async def test_form_already_configured(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result.get("flow_id"), MOCK_USER_INPUT
    )
    await hass.async_block_till_done()
    assert result == snapshot


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_setup_entry: AsyncMock,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test zeroconf discovery triggers the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_SERVICE_INFO,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await _complete_flow_successfully(
        hass, result.get("flow_id"), mock_setup_entry
    )
    assert result == snapshot


async def test_zeroconf_already_configured(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test zeroconf discovery aborts if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_SERVICE_INFO,
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
