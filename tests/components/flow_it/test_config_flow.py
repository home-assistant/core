"""Test the Flow-it config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.flow_it.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


def _get_mock_vmc(
    info_hostname="Flow-it Device",
    state_name="00:11:22:33:44:55",
    exception=None,
):
    """Return a mock FlowItVMCMachine context manager."""
    mock_vmc = AsyncMock()
    mock_vmc.get_info.return_value.hostname = info_hostname
    mock_vmc._state.name = state_name

    if exception:
        mock_vmc.get_info.side_effect = exception

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_vmc
    return mock_cm


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=_get_mock_vmc(),
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
        return_value=_get_mock_vmc(exception=exception),
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


async def test_import(hass: HomeAssistant) -> None:
    """Test import step."""
    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=_get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flow-it Device"
    assert result["data"] == {
        "host": "http://1.1.1.1",
        "username": "api",
        "password": "test-password",
    }


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (FlowItAuthError(), "invalid_auth"),
        (FlowItConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_import_exceptions(
    hass: HomeAssistant, exception: Exception, reason: str
) -> None:
    """Test import step exceptions."""
    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=_get_mock_vmc(exception=exception),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason


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
        return_value=_get_mock_vmc(),
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
        return_value=_get_mock_vmc(exception=exception),
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
        return_value=_get_mock_vmc(state_name="00:11:22:33:44:55"),
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
        return_value=_get_mock_vmc(),
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


async def test_import_with_http(hass: HomeAssistant) -> None:
    """Test import with http:// already in host."""
    with patch(
        "homeassistant.components.flow_it.config_flow.FlowItVMCMachine",
        return_value=_get_mock_vmc(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "http://1.1.1.1",
                "username": "api",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "http://1.1.1.1"


async def test_form_no_unique_id(hass: HomeAssistant) -> None:
    """Test form with no unique_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_vmc = _get_mock_vmc()
    mock_vmc.__aenter__.return_value._state = None

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
