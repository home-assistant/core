"""Fixtures for the Compensation integration."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.compensation.const import (
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_PRECISION,
    CONF_UPPER_LIMIT,
    DEFAULT_DEGREE,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically patch compensation setup_entry."""
    with patch(
        "homeassistant.components.compensation.async_setup_entry",
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
        CONF_ENTITY_ID: "sensor.uncompensated",
        CONF_DATAPOINTS: [
            "1.0, 2.0",
            "2.0, 3.0",
        ],
        CONF_UPPER_LIMIT: False,
        CONF_LOWER_LIMIT: False,
        CONF_PRECISION: 2,
        CONF_DEGREE: DEFAULT_DEGREE,
        CONF_UNIT_OF_MEASUREMENT: "mm",
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the Compensation integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Compensation sensor",
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )
    config_entry.add_to_hass(hass)

    entity_id = get_config[CONF_ENTITY_ID]
    hass.states.async_set(entity_id, 4, {})
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
