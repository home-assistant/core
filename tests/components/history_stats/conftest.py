"""Fixtures for the History stats integration."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.history_stats.const import (
    CONF_END,
    CONF_START,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_STATE, CONF_TYPE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically patch history stats setup."""
    with patch(
        "homeassistant.components.history_stats.async_setup_entry",
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
        CONF_NAME: DEFAULT_NAME,
        CONF_ENTITY_ID: "binary_sensor.test_monitored",
        CONF_STATE: ["on"],
        CONF_TYPE: "count",
        CONF_START: "{{ as_timestamp(utcnow()) - 3600 }}",
        CONF_END: "{{ utcnow() }}",
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the History stats integration in Home Assistant."""
    start_time = dt_util.utcnow() - timedelta(minutes=60)
    t0 = start_time + timedelta(minutes=20)
    t1 = t0 + timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=10)

    def _fake_states(*args, **kwargs):
        return {
            "binary_sensor.test_monitored": [
                State("binary_sensor.test_monitored", "off", last_changed=start_time),
                State("binary_sensor.test_monitored", "on", last_changed=t0),
                State("binary_sensor.test_monitored", "off", last_changed=t1),
                State("binary_sensor.test_monitored", "on", last_changed=t2),
            ]
        }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.recorder.history.state_changes_during_period",
        _fake_states,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await async_update_entity(hass, "sensor.test")
        await hass.async_block_till_done()

    return config_entry
