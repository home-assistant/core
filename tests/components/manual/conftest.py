"""Fixtures for the Manual alarm helper."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.manual.const import (
    CONF_ARMING_STATES,
    CONF_CODE_ARM_REQUIRED,
    DEFAULT_ALARM_NAME,
    DEFAULT_ARMING_TIME,
    DEFAULT_DELAY_TIME,
    DEFAULT_DISARM_AFTER_TRIGGER,
    DEFAULT_TRIGGER_TIME,
    DOMAIN,
    SUPPORTED_ARMING_STATES,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ARMING_TIME,
    CONF_CODE,
    CONF_DELAY_TIME,
    CONF_DISARM_AFTER_TRIGGER,
    CONF_NAME,
    CONF_TRIGGER_TIME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically patch setup."""
    with patch(
        "homeassistant.components.manual.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="get_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """
    return {
        CONF_NAME: DEFAULT_ALARM_NAME,
        CONF_CODE: "1234",
        CONF_CODE_ARM_REQUIRED: True,
        CONF_DELAY_TIME: {"seconds": DEFAULT_DELAY_TIME.total_seconds()},
        CONF_ARMING_TIME: {"seconds": DEFAULT_ARMING_TIME.total_seconds()},
        CONF_TRIGGER_TIME: {"seconds": DEFAULT_TRIGGER_TIME.total_seconds()},
        CONF_DISARM_AFTER_TRIGGER: DEFAULT_DISARM_AFTER_TRIGGER,
        CONF_ARMING_STATES: SUPPORTED_ARMING_STATES,
        "disarmed_trigger_time": {"seconds": 0},
        "armed_home_arming_time": {"seconds": 0},
        "armed_home_delay_time": {"seconds": 0},
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the Manual alarm helper in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ALARM_NAME,
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
