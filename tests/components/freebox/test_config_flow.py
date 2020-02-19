"""Tests for the Freebox config flow."""
import asyncio
from unittest.mock import MagicMock, patch

from aiofreepybox.exceptions import (
    AuthorizationError,
    HttpRequestError,
    InvalidTokenError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.config_entries import SOURCE_DISCOVERY, SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

HOST = "myrouter.freeboxos.fr"
PORT = 1234


@pytest.fixture(name="connect")
def mock_controller_connect():
    """Mock a successful connection."""
    with patch(
        "homeassistant.components.freebox.config_flow.Freepybox"
    ) as service_mock:
        service_mock.return_value.open = MagicMock(return_value=asyncio.Future())
        service_mock.return_value.open.return_value.set_result(None)

        service_mock.return_value.system.get_config = MagicMock(
            return_value=asyncio.Future()
        )
        service_mock.return_value.system.get_config.return_value.set_result(None)

        service_mock.return_value.lan.get_hosts_list = MagicMock(
            return_value=asyncio.Future()
        )
        service_mock.return_value.lan.get_hosts_list.return_value.set_result(None)

        service_mock.return_value.close = MagicMock(return_value=asyncio.Future())
        service_mock.return_value.close.return_value.set_result(None)
        yield service_mock


async def test_user(hass: HomeAssistantType, connect: MagicMock):
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
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_import(hass: HomeAssistantType, connect: MagicMock):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_discovery(hass: HomeAssistantType, connect: MagicMock):
    """Test discovery step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DISCOVERY},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_link(hass: HomeAssistantType, connect: MagicMock):
    """Test linking."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == HOST
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_abort_if_already_setup(hass: HomeAssistantType):
    """Test we abort if component is already setup."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT}, unique_id=HOST
    ).add_to_hass(hass)

    # Should fail, same HOST (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same HOST (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_abort_on_link_failed(hass: HomeAssistantType):
    """Test when we have errors during linking the router."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_PORT: PORT},
    )

    with patch(
        "homeassistant.components.freebox.config_flow.Freepybox.open",
        side_effect=AuthorizationError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "register_failed"}

    with patch(
        "homeassistant.components.freebox.config_flow.Freepybox.open",
        side_effect=HttpRequestError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "connection_failed"}

    with patch(
        "homeassistant.components.freebox.config_flow.Freepybox.open",
        side_effect=InvalidTokenError(),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
