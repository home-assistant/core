"""Define fixtures for Notion tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.notion import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config, unique_id):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=config)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }


@pytest.fixture(name="setup_notion")
async def setup_notion_fixture(hass, config):
    """Define a fixture to set up Notion."""
    with patch("homeassistant.components.notion.async_get_client"), patch(
        "homeassistant.components.notion.config_flow.async_get_client"
    ), patch("homeassistant.components.notion.PLATFORMS", []):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="unique_id")
def unique_id_fixture(hass):
    """Define a config entry unique ID fixture."""
    return "user@host.com"
