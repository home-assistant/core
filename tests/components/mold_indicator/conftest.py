"""Fixtures for the Mold indicator integration."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mold_indicator.const import (
    CONF_CALIBRATION_FACTOR,
    CONF_INDOOR_HUMIDITY,
    CONF_INDOOR_TEMP,
    CONF_OUTDOOR_TEMP,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically path mold indicator."""
    with patch(
        "homeassistant.components.mold_indicator.async_setup_entry",
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
        CONF_INDOOR_TEMP: "sensor.indoor_temp",
        CONF_INDOOR_HUMIDITY: "sensor.indoor_humidity",
        CONF_OUTDOOR_TEMP: "sensor.outdoor_temp",
        CONF_CALIBRATION_FACTOR: 2.0,
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the Mold indicator integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
        title=DEFAULT_NAME,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.indoor_temp",
        "10",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "sensor.outdoor_temp",
        "10",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        "sensor.indoor_humidity", "0", {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )
    await hass.async_block_till_done()

    return config_entry
