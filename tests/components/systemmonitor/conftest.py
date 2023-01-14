"""Fixtures for the Systemmonitor integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch
import uuid

import pytest

from homeassistant.components.systemmonitor.const import CONF_ARG, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_TYPE, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="get_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return default minimal configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """
    return {
        "sensor": [
            {
                CONF_TYPE: "network_in",
                CONF_ARG: "eth0",
                CONF_NAME: "Network in eth0",
                CONF_UNIQUE_ID: "3699ef88-69e6-11ed-a1eb-0242ac120002",
            }
        ],
    }


@pytest.fixture(name="loaded_entry")
async def load_integration(
    hass: HomeAssistant, get_config: dict[str, Any]
) -> MockConfigEntry:
    """Set up the Systemmonitor integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        options=get_config,
        entry_id="1",
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(autouse=True)
def uuid_fixture() -> str:
    """Automatically patch uuid generator."""
    with patch(
        "homeassistant.components.scrape.config_flow.uuid.uuid1",
        return_value=uuid.UUID("3699ef88-69e6-11ed-a1eb-0242ac120002"),
    ):
        yield
