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
    """Test the user flow when the device cannot be connected."""

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


async def test_user_flow_cannot_connect_404(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_bad_session_404
) -> None:
    """Test the user flow when the device cannot be connected."""

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
    """Test the user flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ip_address": ""}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "missing_data"


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


async def test_zeroconf_flow_abort_same_id(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

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
    """Test the zeroconf discovery flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_abort_cannot_connect_404(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_bad_session_404
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_device_error_response(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

    mocker = mock_aiohttp_session

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Snick - Ok, right here we need to figure out how to override the mock for /api/info/get
    # so that it returns bad data or no response. I think we can do it by just defining a new
    # mock, and then that one will override the one in the fixture, but I'm not totally sure
    # how to do it.

    mocker.clear_requests()
    mocker.post(f"http://{TEST_IP}/api/info/get", text="", status=500)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_zeroconf_flow_device_stopped_responding(
    hass: HomeAssistant, setup_mock_config_flow: None, mock_aiohttp_session
) -> None:
    """Test the zeroconf discovery flow with successful configuration."""

    mocker = mock_aiohttp_session

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    async def timeout_side_effect(*args, **kwargs):
        raise TimeoutError

    mocker.clear_requests()
    mocker.post(
        f"http://{TEST_IP}/api/info/get",
        text="",
        side_effect=timeout_side_effect,
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "timeout_connect"
