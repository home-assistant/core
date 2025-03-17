"""Tests for VegeHub config flow."""

from collections.abc import Generator
from ipaddress import ip_address
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.vegehub.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import init_integration
from .conftest import TEST_HOSTNAME, TEST_IP, TEST_SIMPLE_MAC

from tests.common import MockConfigEntry

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address(TEST_IP),
    ip_addresses=[ip_address(TEST_IP)],
    port=80,
    hostname=f"{TEST_HOSTNAME}.local.",
    type="mock_type",
    name="myVege",
    properties={
        zeroconf.ATTR_PROPERTIES_ID: TEST_HOSTNAME,
        "version": "5.1.1",
    },
)


@pytest.fixture(autouse=True)
def setup_mock_config_flow() -> Generator[Any, Any, Any]:
    """Fixture to set up the mock config flow."""
    with (
        patch(
            "socket.gethostname",
            return_value=TEST_HOSTNAME,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[Any, Any, Any]:
    """Prevent the actual integration from being set up."""
    with (
        patch("homeassistant.components.vegehub.async_setup_entry", return_value=True),
        patch("homeassistant.components.vegehub.async_unload_entry", return_value=True),
    ):
        yield


# Tests for flows where the user manually inputs an IP address
async def test_user_flow_success(
    hass: HomeAssistant,
) -> None:
    """Test the user flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"][CONF_MAC] == TEST_SIMPLE_MAC
    assert result["data"][CONF_IP_ADDRESS] == TEST_IP
    assert result["data"][CONF_DEVICE] is not None
    assert result["data"][CONF_WEBHOOK_ID] is not None

    # Since this is user flow, there is no hostname, so hostname should be the IP address
    assert result["data"][CONF_HOST] == TEST_IP

    # Confirm that the entry was created
    entries = hass.config_entries.async_entries(domain=DOMAIN)
    assert len(entries) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_vegehub: MagicMock,
) -> None:
    """Test the user flow with bad data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    type(mock_vegehub).mac_address = PropertyMock(return_value="")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    type(mock_vegehub).mac_address = PropertyMock(return_value=TEST_SIMPLE_MAC)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"][CONF_IP_ADDRESS] == TEST_IP
    assert result["data"][CONF_MAC] == TEST_SIMPLE_MAC


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TimeoutError, "timeout_connect"),
        (ConnectionError, "cannot_connect"),
    ],
)
async def test_user_flow_device_bad_connection_then_success(
    hass: HomeAssistant,
    mock_vegehub: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test the user flow with a timeout."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_vegehub.setup.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"] == {"base": expected_error}

    mock_vegehub.setup.side_effect = None  # Clear the error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"][CONF_IP_ADDRESS] == TEST_IP
    assert result["data"][CONF_MAC] == TEST_SIMPLE_MAC


async def test_user_flow_no_ip_entered(
    hass: HomeAssistant,
) -> None:
    """Test the user flow with blank IP."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_ip"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_bad_ip_entered(
    hass: HomeAssistant,
) -> None:
    """Test the user flow with badly formed IP."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "192.168.0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_ip"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_device(
    hass: HomeAssistant,
) -> None:
    """Test when user flow gets the same device twice."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: TEST_IP}
    )

    assert result["type"] is FlowResultType.ABORT


# Tests for flows that start in zeroconf
async def test_zeroconf_flow_success(
    hass: HomeAssistant,
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Display the confirmation form
    result = await hass.config_entries.flow.async_configure(result["flow_id"], None)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Proceed to creating the entry
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOSTNAME
    assert result["data"][CONF_HOST] == TEST_HOSTNAME
    assert result["data"][CONF_MAC] == TEST_SIMPLE_MAC


async def test_zeroconf_flow_abort_device_asleep(
    hass: HomeAssistant,
    mock_vegehub: MagicMock,
) -> None:
    """Test when zeroconf tries to contact a device that is asleep."""

    mock_vegehub.retrieve_mac_address.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "timeout_connect"


async def test_zeroconf_flow_abort_same_id(
    hass: HomeAssistant,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test when zeroconf gets the same device twice."""

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT


async def test_zeroconf_flow_abort_cannot_connect(
    hass: HomeAssistant,
    mock_vegehub: MagicMock,
) -> None:
    """Test when zeroconf gets bad data."""

    type(mock_vegehub).mac_address = PropertyMock(return_value="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_abort_cannot_connect_404(
    hass: HomeAssistant,
    mock_vegehub: MagicMock,
) -> None:
    """Test when zeroconf gets bad responses."""

    mock_vegehub.retrieve_mac_address.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TimeoutError, "timeout_connect"),
        (ConnectionError, "cannot_connect"),
    ],
)
async def test_zeroconf_flow_device_error_response(
    hass: HomeAssistant,
    mock_vegehub: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test when zeroconf detects the device, but the communication fails at setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Part way through the process, we simulate getting bad responses
    mock_vegehub.setup.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    mock_vegehub.setup.side_effect = None

    # Proceed to creating the entry
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
