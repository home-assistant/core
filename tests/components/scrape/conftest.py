"""Fixtures for the Scrape integration."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD, DEFAULT_VERIFY_SSL
from homeassistant.components.scrape.const import (
    CONF_ENCODING,
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_ENCODING,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_METHOD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import MockRestData

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Automatically path uuid generator."""
    with patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="get_resource_config")
async def get_resource_config_to_integration_load() -> dict[str, Any]:
    """Return default minimal configuration for resource.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """
    return {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: DEFAULT_METHOD,
        "auth": {},
        "advanced": {
            CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_ENCODING: DEFAULT_ENCODING,
        },
    }


@pytest.fixture(name="get_sensor_config")
async def get_sensor_config_to_integration_load() -> tuple[dict[str, Any], ...]:
    """Return default minimal configuration for sensor.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """
    return (
        {
            "data": {"advanced": {}, CONF_INDEX: 0, CONF_SELECT: ".current-version h1"},
            "subentry_id": "01JZN07D8D23994A49YKS649S7",
            "subentry_type": "entity",
            "title": "Current version",
            "unique_id": None,
        },
    )


@pytest.fixture(name="get_data")
async def get_data_to_integration_load() -> MockRestData:
    """Return RestData.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_data", [{...}])
    """
    return MockRestData("test_scrape_sensor")


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant,
    get_resource_config: dict[str, Any],
    get_sensor_config: tuple[dict[str, Any], ...],
    get_data: MockRestData,
) -> MockConfigEntry:
    """Set up the Scrape integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        options=get_resource_config,
        entry_id="01JZN04ZJ9BQXXGXDS05WS7D6P",
        subentries_data=get_sensor_config,
        version=2,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry
