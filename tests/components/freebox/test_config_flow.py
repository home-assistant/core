"""Tests for the Freebox config flow."""
from unittest.mock import Mock, patch

from freebox_api.exceptions import (
    AuthorizationError,
    HttpRequestError,
    InvalidTokenError,
)

from homeassistant import data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import MOCK_HOST, MOCK_PORT

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    host="192.168.0.254",
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


async def test_user(hass: HomeAssistant):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_import(hass: HomeAssistant):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_zeroconf(hass: HomeAssistant):
    """Test zeroconf step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_link(hass: HomeAssistant, router: Mock):
    """Test linking."""
    with patch(
        "homeassistant.components.freebox.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.freebox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        )

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["result"].unique_id == MOCK_HOST
        assert result["title"] == MOCK_HOST
        assert result["data"][CONF_HOST] == MOCK_HOST
        assert result["data"][CONF_PORT] == MOCK_PORT

        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_setup(hass: HomeAssistant):
    """Test we abort if component is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
        unique_id=MOCK_HOST,
    ).add_to_hass(hass)

    # Should fail, same MOCK_HOST (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same MOCK_HOST (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_on_link_failed(hass: HomeAssistant):
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
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "register_failed"}

    with patch(
        "homeassistant.components.freebox.router.Freepybox.open",
        side_effect=HttpRequestError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.freebox.router.Freepybox.open",
        side_effect=InvalidTokenError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
