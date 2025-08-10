"""Tests for the Freebox config flow."""

from ipaddress import ip_address
from unittest.mock import Mock, patch

from freebox_api.exceptions import (
    AuthorizationError,
    HttpRequestError,
    InvalidTokenError,
)

from homeassistant.components.freebox.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.0.254"),
    ip_addresses=[ip_address("192.168.0.254")],
    port=80,
    hostname="Freebox-Server.local.",
    type="_fbx-api._tcp.local.",
    name="Freebox Server._fbx-api._tcp.local.",
    properties={
        "api_version": "8.0",
        "device_type": "FreeboxServer1,2",
        "api_base_url": "/api/",
        "uid": "b15ab20debb399f95001a9ca207d2777",
        "https_available": "1",
        "https_port": f"{MOCK_PORT}",
        "box_model": "fbxgw-r2/full",
        "box_model_name": "Freebox Server (r2)",
        "api_domain": MOCK_HOST,
    },
)


async def test_user(hass: HomeAssistant) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test zeroconf step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"


async def internal_test_link(hass: HomeAssistant) -> None:
    """Test linking internal, common to both router modes."""
    with patch(
        "homeassistant.components.freebox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        )

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == MOCK_HOST
        assert result["title"] == MOCK_HOST
        assert result["data"][CONF_HOST] == MOCK_HOST
        assert result["data"][CONF_PORT] == MOCK_PORT

        assert len(mock_setup_entry.mock_calls) == 1


async def test_link(hass: HomeAssistant, router: Mock) -> None:
    """Test link with standard router mode."""
    await internal_test_link(hass)


async def test_link_bridge_mode(hass: HomeAssistant, router_bridge_mode: Mock) -> None:
    """Test linking for a freebox in bridge mode."""
    await internal_test_link(hass)


async def test_link_bridge_mode_error(
    hass: HomeAssistant, mock_router_bridge_mode_error: Mock
) -> None:
    """Test linking for a freebox in bridge mode, unknown error received from API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if component is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    ).add_to_hass(hass)

    # Should fail, same MOCK_HOST (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_on_link_failed(hass: HomeAssistant) -> None:
    """Test when we have errors during linking the router."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )

    with patch(
        "homeassistant.components.freebox.router.Freepybox.open",
        side_effect=AuthorizationError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "register_failed"}

    with patch(
        "homeassistant.components.freebox.router.Freepybox.open",
        side_effect=HttpRequestError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.freebox.router.Freepybox.open",
        side_effect=InvalidTokenError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}
