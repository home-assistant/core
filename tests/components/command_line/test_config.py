"""The tests for the Command line sensor platform."""
from __future__ import annotations

from typing import Any, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.command_line import DOMAIN
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_NAME = {"name": "Test"}
ENTITY_ID = "sensor.test"


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(DOMAIN, 1)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        **ENTITY_NAME,
                        "command": "echo 5",
                        "unit_of_measurement": "in",
                    },
                },
            },
        ),
    ],
)
async def test_error_in_reload_config(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test Error during reload config service."""
    await start_ha()
    with patch(
        "homeassistant.config.async_hass_config_yaml",
        side_effect=HomeAssistantError("Error reloading config"),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)
        assert "Error reloading config" in caplog.text


@pytest.mark.parametrize(
    "domains, config",
    [
        (
            [(DOMAIN, 0)],
            {
                DOMAIN: {
                    PLATFORM_DOMAIN: {
                        "commands": "echo 5",
                    },
                },
            },
        ),
    ],
)
async def test_error_in_config(
    caplog: Any, hass: HomeAssistant, start_ha: Callable
) -> None:
    """Test async_log_exception during config validation."""
    await start_ha()
    assert (
        "Invalid config for [command_line]: [commands] is an invalid option for [command_line]."
        in caplog.text
    )
