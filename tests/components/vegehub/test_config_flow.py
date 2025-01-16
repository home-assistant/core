"""Tests for VegeHub config flow."""

from ipaddress import ip_address
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.vegehub.config_flow import VegeHubConfigFlow
from homeassistant.components.vegehub.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Mock data for testing
TEST_IP = "192.168.0.100"
TEST_MAC = "A1:B2:C3:D4:E5:F6"
TEST_SIMPLE_MAC = "A1B2C3D4E5F6"
TEST_HOSTNAME = "VegeHub"

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


@pytest.fixture
def setup_mock_config_flow():
    """Fixture to set up the mock config flow."""
    with (
        patch(
            "socket.gethostname",
            return_value=TEST_HOSTNAME,
        ),
    ):
        yield


# Tests for flows where the user manually inputs an IP address
async def test_user_flow_success(
    hass: HomeAssistant, setup_mock_config_flow, mock_vegehub
) -> None:
    """Test the user flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["mac"] == TEST_SIMPLE_MAC
    # Confirm that the entry was created
    entries = hass.config_entries.async_entries(domain=DOMAIN)
    assert len(entries) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test the user flow with bad data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    type(mock_vegehub).mac_address = PropertyMock(return_value="")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_device_timeout_then_success(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test the user flow with bad data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_vegehub.setup.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "error_retry"
    assert "errors" in result
    assert result["errors"] == {"base": "timeout_connect"}

    # Simulate successful retry from error_retry step
    mock_vegehub.setup.side_effect = None  # Clear the error

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["ip_address"] == TEST_IP
    assert result["data"]["mac"] == TEST_SIMPLE_MAC


async def test_user_flow_cannot_connect_404(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test the user flow with bad responses."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_vegehub.setup.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "error_retry"
    assert "errors" in result
    assert result["errors"] == {"base": "cannot_connect"}

    # Simulate successful retry from error_retry step
    mock_vegehub.setup.side_effect = None  # Clear the error

    result = await hass.config_entries.flow.async_configure(result["flow_id"], None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "error_retry"


async def test_user_flow_no_ip_entered(
    hass: HomeAssistant, setup_mock_config_flow, mock_vegehub
) -> None:
    """Test the user flow with blank IP."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_ip"


async def test_user_flow_bad_ip_entered(
    hass: HomeAssistant, setup_mock_config_flow, mock_vegehub
) -> None:
    """Test the user flow with blank IP."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": "192.168.0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_ip"


# Tests for flows that start in zeroconf
async def test_zeroconf_flow_success(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
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
    assert result["data"]["mac"] == TEST_SIMPLE_MAC


async def test_zeroconf_flow_abort_device_asleep(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test when zeroconf gets the same device twice."""

    mock_vegehub.retrieve_mac_address.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "timeout_connect"


async def test_zeroconf_flow_abort_same_id(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test when zeroconf gets the same device twice."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT


async def test_zeroconf_flow_abort_cannot_connect(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test when zeroconf gets bad data."""

    type(mock_vegehub).mac_address = PropertyMock(return_value="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_abort_cannot_connect_404(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test when zeroconf gets bad responses."""

    mock_vegehub.retrieve_mac_address.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_device_error_response(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test when zeroconf detects the device, but the communication fails at setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Part way through the process, we simulate getting bad responses
    mock_vegehub.setup.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_zeroconf_flow_device_stopped_responding(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_vegehub
) -> None:
    """Test when the zeroconf detects a device, but then the device goes to sleep before setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Part way through the test we simulate getting timeouts
    mock_vegehub.setup.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "timeout_connect"


async def test_async_create_entry_hub_none(hass: HomeAssistant) -> None:
    """Test _async_create_entry aborts when self._hub is None."""

    # Set up a base URL for the test
    hass.config.internal_url = "http://example.local"

    # Create an instance of the config flow
    flow = VegeHubConfigFlow()
    flow.hass = hass

    # Simulate a situation where self._hub is None
    flow._hub = None

    # Call _async_create_entry and expect it to abort
    result = await flow._async_create_entry()

    assert result["type"] == "abort"
    assert result["reason"] == "unknown_error"
