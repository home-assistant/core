"""Shared pytest fixtures for the Noonlight tests."""

from __future__ import annotations

import pytest

from homeassistant.components.noonlight.const import (
    ALL_NOONLIGHT_SERVICES,
    CONF_ADDRESS,
    CONF_API_TOKEN,
    CONF_CITY,
    CONF_DEDUPE_SECONDS,
    CONF_DEFAULT_ENTRY_DELAY,
    CONF_ENVIRONMENT,
    CONF_NAME,
    CONF_PHONE,
    CONF_SERVICES_GRANTED,
    CONF_STATE,
    CONF_ZIP,
    DOMAIN,
    ENV_SANDBOX,
)

from tests.common import MockConfigEntry

# Base URL for the sandbox environment the test entries target.
SANDBOX = "https://api-sandbox.noonlight.com"


@pytest.fixture
def caller_data() -> dict:
    """Caller/location block used by the config entry."""
    return {
        CONF_NAME: "Main",
        CONF_PHONE: "+15555550123",
        CONF_ADDRESS: "1 Test St",
        CONF_CITY: "Testville",
        CONF_STATE: "CA",
        CONF_ZIP: "90001",
    }


@pytest.fixture
def config_entry(caller_data: dict) -> MockConfigEntry:
    """A sandbox config entry titled 'Main'."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        entry_id="noonlighttest",
        data={
            CONF_API_TOKEN: "test-token",
            CONF_ENVIRONMENT: ENV_SANDBOX,
            **caller_data,
        },
        options={
            CONF_DEFAULT_ENTRY_DELAY: 30,
            CONF_DEDUPE_SECONDS: 300,
            CONF_SERVICES_GRANTED: ALL_NOONLIGHT_SERVICES,
        },
    )


@pytest.fixture
async def setup_entry(hass, config_entry: MockConfigEntry):
    """Add the entry to hass and set up the integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
