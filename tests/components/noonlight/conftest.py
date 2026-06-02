"""Shared pytest fixtures for the Noonlight tests."""

from __future__ import annotations

from httpx import Response
import pytest
import respx

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
        # Address-based unique id (environment + street + ZIP); see
        # config_flow._location_unique_id.
        unique_id="sandbox_1_test_st_90001",
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
    """Add the entry to hass and set up the integration.

    Setup now performs a connectivity probe (test-before-setup), so the GET
    status route must be mocked. This nested respx context is isolated from
    any ``@respx.mock`` on the test body, which only activates after fixtures
    resolve.
    """
    config_entry.add_to_hass(hass)
    with respx.mock:
        respx.get(url__regex=r".*/dispatch/v1/alarms/.*/status").mock(
            return_value=Response(404)
        )
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry
