"""Test the Flow-it config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.flow_it.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import get_mock_vmc

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    "host": "1.1.1.1",
    "username": "api",
    "password": "test-password",
}


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {**USER_INPUT, "host": "http://1.1.1.1"}
    assert result["result"].unique_id == "00:11:22:33:44:55"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_user_flow_exceptions(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test we handle exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(exception=exception),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {**USER_INPUT, "host": "http://1.1.1.1"}
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_zeroconf(hass: HomeAssistant) -> None:
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
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"name": "mock_name"}

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {
        "host": "http://mock_hostname.local",
        "username": "api",
        "password": "test-password",
    }
    assert result["result"].unique_id == "00:11:22:33:44:55"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_zeroconf_exceptions(
    hass: HomeAssistant, exception: Exception, error: str
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

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(exception=exception),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "api",
                "password": "test-password",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {
        "host": "http://mock_hostname.local",
        "username": "api",
        "password": "test-password",
    }
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Test user already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:11:22:33:44:55",
        data={"host": "http://1.1.1.1", "username": "api", "password": "old"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(state_name="00:11:22:33:44:55"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf already configured aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:11:22:33:44:55",
        data={
            "host": "http://mock_hostname.local",
            "username": "api",
            "password": "old",
        },
    )
    entry.add_to_hass(hass)

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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_with_http(hass: HomeAssistant) -> None:
    """Test form with http:// already in host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**USER_INPUT, "host": "http://1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "http://1.1.1.1"
    assert result["result"].unique_id == "00:11:22:33:44:55"
