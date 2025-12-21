"""Fixtures for the Statistics integration."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.statistics import DOMAIN
from homeassistant.components.statistics.sensor import (
    CONF_KEEP_LAST_SAMPLE,
    CONF_MAX_AGE,
    CONF_PERCENTILE,
    CONF_PRECISION,
    CONF_SAMPLES_MAX_BUFFER_SIZE,
    CONF_STATE_CHARACTERISTIC,
    DEFAULT_NAME,
    STAT_AVERAGE_LINEAR,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from .test_sensor import VALUES_NUMERIC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically path uuid generator."""
    with patch(
        "homeassistant.components.statistics.async_setup_entry",
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
        CONF_ENTITY_ID: "sensor.test_monitored",
        CONF_STATE_CHARACTERISTIC: STAT_AVERAGE_LINEAR,
        CONF_SAMPLES_MAX_BUFFER_SIZE: 20.0,
        CONF_MAX_AGE: {"hours": 8, "minutes": 5, "seconds": 5},
        CONF_KEEP_LAST_SAMPLE: False,
        CONF_PERCENTILE: 50.0,
        CONF_PRECISION: 2.0,
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the Statistics integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    return config_entry
