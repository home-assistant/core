"""Tests for VegeHub config flow."""

from ipaddress import ip_address
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.vegehub.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Mock data for testing
TEST_IP = "192.168.0.100"
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


@pytest.fixture
def mock_setup_entry():
    """Prevent the actual integration from being set up."""
    with (
        patch("homeassistant.components.vegehub.async_setup_entry", return_value=True),
        patch("homeassistant.components.vegehub.async_unload_entry", return_value=True),
    ):
        yield


# Tests for flows where the user manually inputs an IP address
async def test_user_flow_success(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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

    type(mock_vegehub).mac_address = PropertyMock(return_value=TEST_SIMPLE_MAC)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["ip_address"] == TEST_IP
    assert result["data"]["mac"] == TEST_SIMPLE_MAC


async def test_user_flow_device_timeout_then_success(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the user flow with a timeout."""

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
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"] == {"base": "timeout_connect"}

    mock_vegehub.setup.side_effect = None  # Clear the error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["ip_address"] == TEST_IP
    assert result["data"]["mac"] == TEST_SIMPLE_MAC


async def test_user_flow_cannot_connect_404(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"] == {"base": "cannot_connect"}

    mock_vegehub.setup.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["ip_address"] == TEST_IP
    assert result["data"]["mac"] == TEST_SIMPLE_MAC


async def test_user_flow_no_ip_entered(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_user_flow_bad_ip_entered(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test the user flow with badly formed IP."""

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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


# Tests for flows that start in zeroconf
async def test_zeroconf_flow_success(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
) -> None:
    """Test when zeroconf gets bad responses."""

    mock_vegehub.retrieve_mac_address.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_device_error_response(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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

    mock_vegehub.setup.side_effect = None

    # Proceed to creating the entry
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_flow_device_stopped_responding(
    hass: HomeAssistant,
    setup_mock_config_flow: None,
    mock_vegehub: MagicMock,
    mock_setup_entry: None,
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

    mock_vegehub.setup.side_effect = None

    # Proceed to creating the entry
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
