"""Tests for Logger Websocket API commands."""

import logging
from unittest.mock import patch

from homeassistant import config_entries, loader
from homeassistant.components.logger.helpers import DATA_LOGGER
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockModule,
    MockUser,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator


async def test_integration_log_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test fetching integration log info."""

    assert await async_setup_component(hass, "logger", {})

    logging.getLogger("homeassistant.components.http").setLevel(logging.DEBUG)
    logging.getLogger("homeassistant.components.websocket_api").setLevel(logging.DEBUG)

    websocket_client = await hass_ws_client()
    await websocket_client.send_json({"id": 7, "type": "logger/log_info"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert {"domain": "http", "level": logging.DEBUG} in msg["result"]


async def test_integration_log_info_discovered_flows(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test that log info includes discovered flows."""
    assert await async_setup_component(hass, "logger", {})

    # Set up a discovery flow (zeroconf)
    mock_integration(hass, MockModule("discovered_integration"))
    mock_platform(hass, "discovered_integration.config_flow", None)

    class DiscoveryFlow(config_entries.ConfigFlow, domain="discovered_integration"):
        """Test discovery flow."""

        VERSION = 1

        async def async_step_zeroconf(self, discovery_info=None):
            """Test zeroconf step."""
            return self.async_show_form(step_id="zeroconf")

    # Set up a user flow (non-discovery)
    mock_integration(hass, MockModule("user_flow_integration"))
    mock_platform(hass, "user_flow_integration.config_flow", None)

    class UserFlow(config_entries.ConfigFlow, domain="user_flow_integration"):
        """Test user flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return self.async_show_form(step_id="user")

    with (
        mock_config_flow("discovered_integration", DiscoveryFlow),
        mock_config_flow("user_flow_integration", UserFlow),
    ):
        # Start both flows
        await hass.config_entries.flow.async_init(
            "discovered_integration",
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        await hass.config_entries.flow.async_init(
            "user_flow_integration",
            context={"source": config_entries.SOURCE_USER},
        )

        # Verify both flows are in progress
        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 2

        websocket_client = await hass_ws_client()
        await websocket_client.send_json({"id": 7, "type": "logger/log_info"})

        msg = await websocket_client.receive_json()
        assert msg["id"] == 7
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]

        domains = [item["domain"] for item in msg["result"]]
        # Discovery flow should be included
        assert "discovered_integration" in domains
        # User flow should NOT be included (not a discovery source)
        assert "user_flow_integration" not in domains


async def test_integration_log_info_with_settings(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test that log info includes integrations with custom log settings."""
    assert await async_setup_component(hass, "logger", {})

    # Set up a mock integration that is not loaded
    mock_integration(hass, MockModule("unloaded_integration"))

    # Set a log level for this unloaded integration
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 1,
            "type": "logger/integration_log_level",
            "integration": "unloaded_integration",
            "level": "DEBUG",
            "persistence": "none",
        }
    )
    msg = await websocket_client.receive_json()
    assert msg["success"]

    # Now check log_info includes the unloaded integration with settings
    await websocket_client.send_json({"id": 2, "type": "logger/log_info"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 2
    assert msg["success"]

    domains = [item["domain"] for item in msg["result"]]
    assert "unloaded_integration" in domains


async def test_integration_log_level_logger_not_loaded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test setting integration log level."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logger/log_level",
            "integration": "websocket_api",
            "level": logging.DEBUG,
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]


async def test_integration_log_level(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test setting integration log level."""
    websocket_client = await hass_ws_client()
    assert await async_setup_component(hass, "logger", {})

    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logger/integration_log_level",
            "integration": "websocket_api",
            "level": "DEBUG",
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert hass.data[DATA_LOGGER].overrides == {
        "homeassistant.components.websocket_api": logging.DEBUG
    }


async def test_custom_integration_log_level(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test setting integration log level."""
    websocket_client = await hass_ws_client()
    assert await async_setup_component(hass, "logger", {})

    integration = loader.Integration(
        hass,
        "custom_components.hue",
        None,
        {
            "name": "Hue",
            "dependencies": [],
            "requirements": [],
            "domain": "hue",
            "loggers": ["some_other_logger"],
        },
    )

    with (
        patch(
            "homeassistant.components.logger.helpers.async_get_integration",
            return_value=integration,
        ),
        patch(
            "homeassistant.components.logger.websocket_api.async_get_integration",
            return_value=integration,
        ),
    ):
        await websocket_client.send_json(
            {
                "id": 7,
                "type": "logger/integration_log_level",
                "integration": "hue",
                "level": "DEBUG",
                "persistence": "none",
            }
        )

        msg = await websocket_client.receive_json()
        assert msg["id"] == 7
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]

        assert hass.data[DATA_LOGGER].overrides == {
            "homeassistant.components.hue": logging.DEBUG,
            "custom_components.hue": logging.DEBUG,
            "some_other_logger": logging.DEBUG,
        }


async def test_integration_log_level_unknown_integration(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test setting integration log level for an unknown integration."""
    websocket_client = await hass_ws_client()
    assert await async_setup_component(hass, "logger", {})

    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logger/integration_log_level",
            "integration": "websocket_api_123",
            "level": "DEBUG",
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]


async def test_module_log_level(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test setting integration log level."""
    websocket_client = await hass_ws_client()
    assert await async_setup_component(
        hass,
        "logger",
        {"logger": {"logs": {"homeassistant.components.other_component": "warning"}}},
    )

    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logger/log_level",
            "module": "homeassistant.components.websocket_api",
            "level": "DEBUG",
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert hass.data[DATA_LOGGER].overrides == {
        "homeassistant.components.websocket_api": logging.DEBUG,
        "homeassistant.components.other_component": logging.WARNING,
    }


async def test_module_log_level_override(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_admin_user: MockUser
) -> None:
    """Test override yaml integration log level."""
    websocket_client = await hass_ws_client()
    assert await async_setup_component(
        hass,
        "logger",
        {"logger": {"logs": {"homeassistant.components.websocket_api": "warning"}}},
    )

    assert hass.data[DATA_LOGGER].overrides == {
        "homeassistant.components.websocket_api": logging.WARNING
    }

    await websocket_client.send_json(
        {
            "id": 6,
            "type": "logger/log_level",
            "module": "homeassistant.components.websocket_api",
            "level": "ERROR",
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert hass.data[DATA_LOGGER].overrides == {
        "homeassistant.components.websocket_api": logging.ERROR
    }

    await websocket_client.send_json(
        {
            "id": 7,
            "type": "logger/log_level",
            "module": "homeassistant.components.websocket_api",
            "level": "DEBUG",
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert hass.data[DATA_LOGGER].overrides == {
        "homeassistant.components.websocket_api": logging.DEBUG
    }

    await websocket_client.send_json(
        {
            "id": 8,
            "type": "logger/log_level",
            "module": "homeassistant.components.websocket_api",
            "level": "NOTSET",
            "persistence": "none",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 8
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]

    assert hass.data[DATA_LOGGER].overrides == {
        "homeassistant.components.websocket_api": logging.NOTSET
    }
