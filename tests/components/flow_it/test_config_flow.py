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


async def test_form(hass: HomeAssistant) -> None:
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Flow-it Device"
    assert result2["data"] == {
        "host": "http://1.1.1.1",
        "username": "api",
        "password": "test-password",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_form_exceptions(
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error}


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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Flow-it Device"
    assert result2["data"] == {
        "host": "http://mock_hostname",
        "username": "api",
        "password": "test-password",
    }


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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "username": "api",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error}


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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test zeroconf already configured aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:11:22:33:44:55",
        data={"host": "http://mock_hostname", "username": "api", "password": "old"},
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


async def test_form_with_http(hass: HomeAssistant) -> None:
    """Test form with http:// already in host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"]["host"] == "http://1.1.1.1"


async def test_form_no_unique_id(hass: HomeAssistant) -> None:
    """Test form with no unique_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_vmc = get_mock_vmc()
    mock_vmc.__aenter__.return_value.state = None

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=mock_vmc,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flow-it Device",
        unique_id="00:11:22:33:44:55",
        data={
            "host": "http://1.1.1.1",
            "username": "api",
            "password": "old_password",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "api",
                "password": "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data["password"] == "new_password"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_reauth_exceptions(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test reauth flow exceptions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flow-it Device",
        unique_id="00:11:22:33:44:55",
        data={
            "host": "http://1.1.1.1",
            "username": "api",
            "password": "old_password",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=get_mock_vmc(exception=exception),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "api",
                "password": "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"]["base"] == error
