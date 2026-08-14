"""Test the air-Q config flow."""

from ipaddress import IPv4Address
from unittest.mock import AsyncMock

from aioairq import InvalidAuth
from aiohttp.client_exceptions import ClientConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.airq.const import (
    CONF_CLIP_NEGATIVE,
    CONF_RETURN_AVERAGE,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .common import TEST_DEVICE_INFO, TEST_USER_DATA

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=IPv4Address("192.168.0.123"),
    ip_addresses=[IPv4Address("192.168.0.123")],
    port=80,
    hostname="airq.local.",
    type="_http._tcp.local.",
    name="air-Q._http._tcp.local.",
    properties={"device": "air-q", "devicename": "My air-Q", "id": "test-serial-123"},
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

DEFAULT_OPTIONS = {
    CONF_CLIP_NEGATIVE: True,
    CONF_RETURN_AVERAGE: True,
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_airq: AsyncMock,
) -> None:
    """Test successful user config flow from start to entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_DATA,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_INFO["name"]
    assert result["data"] == TEST_USER_DATA
    assert result["result"].unique_id == TEST_DEVICE_INFO["id"]


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidAuth, "invalid_auth"),
        (ClientConnectionError, "cannot_connect"),
    ],
)
async def test_user_flow_errors_recover(
    hass: HomeAssistant,
    mock_airq: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow recovers from errors and completes successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_airq.validate.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover: correct input on retry
    mock_airq.validate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_INFO["name"]
    assert result["data"] == TEST_USER_DATA


async def test_duplicate_error(
    hass: HomeAssistant,
    mock_airq: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that errors are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "user_input", [{}, {CONF_RETURN_AVERAGE: False}, {CONF_CLIP_NEGATIVE: False}]
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict,
) -> None:
    """Test that the options flow works."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert mock_config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == mock_config_entry.options == DEFAULT_OPTIONS | user_input


async def test_zeroconf_discovery(hass: HomeAssistant, mock_airq: AsyncMock) -> None:
    """Test zeroconf discovery and successful setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My air-Q"
    assert result["result"].unique_id == "test-serial-123"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.0.123",
        CONF_PASSWORD: "password",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidAuth, "invalid_auth"),
        (ClientConnectionError, "cannot_connect"),
    ],
)
async def test_zeroconf_discovery_errors(
    hass: HomeAssistant,
    mock_airq: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test zeroconf discovery with invalid password or connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    mock_airq.validate.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover: correct password on retry
    mock_airq.validate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "correct_password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My air-Q"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.0.123",
        CONF_PASSWORD: "correct_password",
    }


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant, mock_airq: AsyncMock
) -> None:
    """Test zeroconf discovery aborts if device is already configured."""
    MockConfigEntry(
        data=TEST_USER_DATA,
        domain=DOMAIN,
        unique_id="test-serial-123",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_updates_ip_on_already_configured(
    hass: HomeAssistant, mock_airq: AsyncMock
) -> None:
    """Test zeroconf updates the IP address if device is already configured."""
    entry = MockConfigEntry(
        data={CONF_IP_ADDRESS: "192.168.0.1", CONF_PASSWORD: "password"},
        domain=DOMAIN,
        unique_id="test-serial-123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "192.168.0.123"


async def test_user_flow_succeeds_during_zeroconf_discovery(
    hass: HomeAssistant, mock_airq: AsyncMock
) -> None:
    """Test manual user flow does not abort when a zeroconf flow is in progress.

    Regression test: before raise_on_progress=False, initiating a manual
    setup while zeroconf discovery was pending for the same device would
    abort with ``already_in_progress``.
    """
    # 1. Start a zeroconf discovery flow — this sets unique_id and waits
    #    for the user to confirm (enter password).
    zeroconf_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=IPv4Address("192.168.0.123"),
            ip_addresses=[IPv4Address("192.168.0.123")],
            port=80,
            hostname="airq.local.",
            type="_http._tcp.local.",
            name="air-Q._http._tcp.local.",
            # Use the same ID as TEST_DEVICE_INFO so both flows share
            # the unique_id.
            properties={
                "device": "air-q",
                "devicename": "My air-Q",
                "id": TEST_DEVICE_INFO["id"],
            },
        ),
    )
    assert zeroconf_result["type"] is FlowResultType.FORM
    assert zeroconf_result["step_id"] == "discovery_confirm"

    # 2. While the zeroconf flow is pending, start a manual user flow.
    user_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_result["type"] is FlowResultType.FORM

    # 3. Complete the manual flow — this should NOT abort with
    #    "already_in_progress".
    user_result2 = await hass.config_entries.flow.async_configure(
        user_result["flow_id"], TEST_USER_DATA
    )
    await hass.async_block_till_done()

    assert user_result2["type"] is FlowResultType.CREATE_ENTRY
    assert user_result2["title"] == TEST_DEVICE_INFO["name"]
    assert user_result2["data"] == TEST_USER_DATA

    # 4. The zeroconf discovery flow should now be aborted: completing
    #    the user flow created a config entry for this unique_id, so
    #    the pending discovery flow is no longer valid.
    ongoing_flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert not ongoing_flows, f"Expected no remaining flows, but found: {ongoing_flows}"


async def test_zeroconf_discovery_missing_id(
    hass: HomeAssistant, mock_airq: AsyncMock
) -> None:
    """Test zeroconf discovery aborts if device ID is missing from properties."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address("192.168.0.123"),
        ip_addresses=[IPv4Address("192.168.0.123")],
        port=80,
        hostname="airq.local.",
        type="_http._tcp.local.",
        name="air-Q._http._tcp.local.",
        properties={"device": "air-q", "devicename": "My air-Q"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "incomplete_discovery"
