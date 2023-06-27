"""Fixtures for the Scrape integration."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

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
    CONF_NAME,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from . import MockRestData

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Automatically path uuid generator."""
    with patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="get_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return default minimal configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """
    return {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: DEFAULT_METHOD,
        CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_ENCODING: DEFAULT_ENCODING,
        "sensor": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0,
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }


@pytest.fixture(name="get_data")
async def get_data_to_integration_load() -> MockRestData:
    """Return RestData.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_data", [{...}])
    """
    return MockRestData("test_scrape_sensor")


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any], get_data: MockRestData
) -> MockConfigEntry:
    """Set up the Scrape integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(autouse=True)
def uuid_fixture() -> str:
    """Automatically path uuid generator."""
    with patch(
        "homeassistant.components.scrape.config_flow.uuid.uuid1",
        return_value=uuid.UUID("3699ef88-69e6-11ed-a1eb-0242ac120002"),
    ):
        yield
