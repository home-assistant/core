"""Tests for VegeHub config flow."""

from ipaddress import ip_address
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import zeroconf
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


async def test_user_flow_success(
    hass: HomeAssistant, setup_mock_config_flow, mock_aiohttp_session
) -> None:
    """Test the user flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_IP
    assert result["data"]["mac"] == TEST_SIMPLE_MAC
    # Confirm that the entry was created
    entries = hass.config_entries.async_entries(domain=DOMAIN)
    assert len(entries) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_bad_session
) -> None:
    """Test the user flow with bad data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_device_timeout(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the user flow with bad data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mocker = mock_aiohttp_session

    async def timeout_side_effect(*args, **kwargs):
        raise TimeoutError

    mocker.clear_requests()
    mocker.post(
        f"http://{TEST_IP}/api/info/get",
        text="",
        side_effect=timeout_side_effect,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "timeout_connect"


async def test_user_flow_cannot_connect_404(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_bad_session_404
) -> None:
    """Test the user flow with bad responses."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": TEST_IP}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_no_ip_entered(
    hass: HomeAssistant, setup_mock_config_flow, mock_aiohttp_session
) -> None:
    """Test the user flow with blank IP."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": ""}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_ip"


async def test_user_flow_bad_ip_entered(
    hass: HomeAssistant, setup_mock_config_flow, mock_aiohttp_session
) -> None:
    """Test the user flow with blank IP."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": "192.168.0"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_ip"


async def test_zeroconf_flow_success(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOSTNAME
    assert result["data"]["mac"] == TEST_SIMPLE_MAC


async def test_zeroconf_flow_abort_device_asleep(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test when zeroconf gets the same device twice."""

    mocker = mock_aiohttp_session

    async def timeout_side_effect(*args, **kwargs):
        raise TimeoutError

    mocker.clear_requests()
    mocker.post(
        f"http://{TEST_IP}/api/info/get",
        text="",
        side_effect=timeout_side_effect,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "timeout_connect"


async def test_zeroconf_flow_abort_same_id(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test when zeroconf gets the same device twice."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.ABORT


async def test_zeroconf_flow_abort_cannot_connect(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_bad_session
) -> None:
    """Test when zeroconf gets bad data."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_abort_cannot_connect_404(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_bad_session_404
) -> None:
    """Test when zeroconf gets bad responses."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_device_error_response(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test when zeroconf detects the device, but the communication fails at setup."""

    mocker = mock_aiohttp_session

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Part way through the process, we simulate getting bad responses
    mocker.clear_requests()
    mocker.post(f"http://{TEST_IP}/api/config/get", json={}, status=500)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_zeroconf_flow_device_stopped_responding(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test when the zeroconf detects a device, but then the device goes to sleep before setup."""

    mocker = mock_aiohttp_session

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    async def timeout_side_effect(*args, **kwargs):
        raise TimeoutError

    # Part way through the test we simulate getting timeouts
    mocker.clear_requests()
    mocker.post(
        f"http://{TEST_IP}/api/config/get",
        text="",
        side_effect=timeout_side_effect,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "timeout_connect"
