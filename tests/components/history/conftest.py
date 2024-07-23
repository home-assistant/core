"""Fixtures for history tests."""

import pytest

from homeassistant.components import history
from homeassistant.components.recorder import Recorder
from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import RecorderInstanceGenerator


@pytest.fixture
async def mock_recorder_before_hass(
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


@pytest.fixture
async def hass_history(hass: HomeAssistant, recorder_mock: Recorder) -> None:
    """Home Assistant fixture with history."""
    config = history.CONFIG_SCHEMA(
        {
            history.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["media_player"],
                    CONF_ENTITIES: ["thermostat.test"],
                },
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["thermostat"],
                    CONF_ENTITIES: ["media_player.test"],
                },
            }
        }
    )
    assert await async_setup_component(hass, history.DOMAIN, config)
