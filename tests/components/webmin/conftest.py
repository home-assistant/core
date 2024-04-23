"""Fixtures for Webmin integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.webmin.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_USER_INPUT = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.webmin.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


async def async_init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Webmin integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, options=TEST_USER_INPUT, title="name")
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.webmin.helpers.WebminInstance.update",
        return_value=load_json_object_fixture("webmin_update.json", DOMAIN),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
