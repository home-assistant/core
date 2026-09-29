"""Test the Flow-it config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.flow_it.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    "host": "1.1.1.1",
    "username": "api",
    "password": "test-password",
}


async def test_user_flow(hass: HomeAssistant, mock_flow_it: AsyncMock) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {**USER_INPUT, "host": f"http://{USER_INPUT['host']}"}
    assert result["result"].unique_id == "001122334455"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_user_flow_exceptions(
    hass: HomeAssistant, mock_flow_it: AsyncMock, exception: Exception, error: str
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_flow_it.return_value.refresh_state.side_effect = exception
    mock_flow_it.return_value.get_info.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_flow_it.return_value.refresh_state.side_effect = None
    mock_flow_it.return_value.get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {**USER_INPUT, "host": f"http://{USER_INPUT['host']}"}
    assert result["result"].unique_id == "001122334455"


async def test_zeroconf(hass: HomeAssistant, mock_flow_it: AsyncMock) -> None:
    """Test zeroconf discovery."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("1.1.1.1"),
        ip_addresses=[ip_address("1.1.1.1")],
        port=80,
        hostname="mock_hostname.local.",
        type="_tbk_vmc._tcp.local.",
        name="mock_name",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"name": "mock_name"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "username": "api",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {
        "host": "http://mock_hostname.local",
        "username": "api",
        "password": "test-password",
    }
    assert result["result"].unique_id == "001122334455"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_zeroconf_exceptions(
    hass: HomeAssistant, mock_flow_it: AsyncMock, exception: Exception, error: str
) -> None:
    """Test zeroconf exceptions."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("1.1.1.1"),
        ip_addresses=[ip_address("1.1.1.1")],
        port=80,
        hostname="mock_hostname.local.",
        type="_tbk_vmc._tcp.local.",
        name="mock_name",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_flow_it.return_value.refresh_state.side_effect = exception
    mock_flow_it.return_value.get_info.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "username": "api",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_flow_it.return_value.refresh_state.side_effect = None
    mock_flow_it.return_value.get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "username": "api",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {
        "host": "http://mock_hostname.local",
        "username": "api",
        "password": "test-password",
    }
    assert result["result"].unique_id == "001122334455"


async def test_user_already_configured(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test user already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf already configured aborts."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("1.1.1.1"),
        ip_addresses=[ip_address("1.1.1.1")],
        port=80,
        hostname="mock_hostname.local.",
        type="_tbk_vmc._tcp.local.",
        name="mock_name",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_with_http(
    hass: HomeAssistant, mock_flow_it: AsyncMock
) -> None:
    """Test form with http:// already in host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, "host": f"http://{USER_INPUT['host']}"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {**USER_INPUT, "host": f"http://{USER_INPUT['host']}"}
    assert result["result"].unique_id == "001122334455"
