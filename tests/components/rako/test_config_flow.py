"""Test the Rako config flow."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from python_rako import RAKO_BRIDGE_DEFAULT_PORT, Bridge

from homeassistant import data_entry_flow
from homeassistant.components.rako import config_flow
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_UNIQUE_ID,
)

from . import MOCK_BRIDGE_DESC


@pytest.fixture
def rako_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.RakoConfigFlow()
    flow.rako_timeout = 0.5
    flow.hass = hass
    flow.context = {}
    return flow


async def test_user_config_flow_initial_w_discovery(hass, rako_flow):
    """Test the initial click with bridge discovery."""
    with patch(
        "homeassistant.components.rako.config_flow.discover_bridge",
        return_value=MOCK_BRIDGE_DESC,
    ) as discover_bridge_mock:
        result = await rako_flow.async_step_user()

        discover_bridge_mock.assert_awaited_once()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


async def test_user_config_flow_initial_w_failed_discovery(hass, rako_flow):
    """Test the initial click with failed bridge discovery."""

    async def fn():
        raise ValueError("foobar")

    with patch(
        "homeassistant.components.rako.config_flow.discover_bridge", side_effect=fn
    ) as discover_bridge_mock:
        result = await rako_flow.async_step_user()

        discover_bridge_mock.assert_awaited_once()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_BASE] == "no_devices_found"


async def test_user_config_flow_initial_w_timeout_discovery(hass, rako_flow):
    """Test the initial click with failed bridge discovery."""

    async def fn():
        await asyncio.sleep(6)

    with patch(
        "homeassistant.components.rako.config_flow.discover_bridge", side_effect=fn
    ) as discover_bridge_mock:
        result = await rako_flow.async_step_user()

        discover_bridge_mock.assert_awaited_once()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_BASE] == "no_devices_found"


async def test_user_config_flow_bad_input(hass, rako_flow):
    """Submit bad IP."""

    class MockBridge(Bridge):
        async def get_rako_xml(self, session) -> str:
            return "<badxml></badxml>"

    with patch(
        "homeassistant.components.rako.config_flow.discover_bridge",
        return_value=MOCK_BRIDGE_DESC,
    ) as discover_bridge_mock, patch(
        "homeassistant.components.rako.config_flow.Bridge", side_effect=MockBridge
    ):
        result = await rako_flow.async_step_user(
            {
                CONF_HOST: "a.bad.ip.addr",
                CONF_PORT: RAKO_BRIDGE_DEFAULT_PORT,
                CONF_MAC: "",
                CONF_NAME: "",
            }
        )

        discover_bridge_mock.assert_not_awaited()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_BASE] == "cannot_connect"


async def test_user_config_flow_good_input(hass, rako_flow):
    """Submit good IP."""
    with patch(
        "homeassistant.components.rako.config_flow.discover_bridge",
        return_value=MOCK_BRIDGE_DESC,
    ) as discover_bridge_mock:
        with patch("homeassistant.components.rako.config_flow.Bridge") as MockBridge:
            bridge_info = SimpleNamespace(hostMAC="whatever")
            expected_unique_id = MOCK_BRIDGE_DESC["mac"]

            MockBridge().get_info = AsyncMock(return_value=bridge_info)
            result = await rako_flow.async_step_user(MOCK_BRIDGE_DESC)

            discover_bridge_mock.assert_not_awaited()
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert MOCK_BRIDGE_DESC["name"] in result["title"]
            assert result["data"] == MOCK_BRIDGE_DESC
            assert rako_flow.context[CONF_UNIQUE_ID] == expected_unique_id
            assert rako_flow.unique_id == expected_unique_id
