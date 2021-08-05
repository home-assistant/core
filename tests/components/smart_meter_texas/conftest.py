"""Test configuration and mocks for Smart Meter Texas."""
import asyncio
import json
from pathlib import Path

import pytest
from smart_meter_texas.const import (
    AUTH_ENDPOINT,
    BASE_ENDPOINT,
    BASE_URL,
    LATEST_OD_READ_ENDPOINT,
    METER_ENDPOINT,
    OD_READ_ENDPOINT,
)

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.smart_meter_texas.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

TEST_ENTITY_ID = "sensor.electric_meter_123456789"


def load_smt_fixture(name):
    """Return a dict of the json fixture."""
    json_fixture = load_fixture(Path() / DOMAIN / f"{name}.json")
    return json.loads(json_fixture)


async def setup_integration(hass, config_entry, aioclient_mock, **kwargs):
    """Initialize the Smart Meter Texas integration for testing."""
    mock_connection(aioclient_mock, **kwargs)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def refresh_data(hass, config_entry, aioclient_mock):
    """Request a DataUpdateCoordinator refresh."""
    mock_connection(aioclient_mock)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()


def mock_connection(
    aioclient_mock, auth_fail=False, auth_timeout=False, bad_reading=False
):
    """Mock all calls to the API."""
    aioclient_mock.get(BASE_URL)

    auth_endpoint = f"{BASE_ENDPOINT}{AUTH_ENDPOINT}"
    if not auth_fail and not auth_timeout:
        aioclient_mock.post(
            auth_endpoint,
            json={"token": "token123"},
        )
    elif auth_fail:
        aioclient_mock.post(
            auth_endpoint,
            status=400,
            json={"errormessage": "ERR-USR-INVALIDPASSWORDERROR"},
        )
    else:  # auth_timeout
        aioclient_mock.post(auth_endpoint, exc=asyncio.TimeoutError)

    aioclient_mock.post(
        f"{BASE_ENDPOINT}{METER_ENDPOINT}",
        json=load_smt_fixture("meter"),
    )
    aioclient_mock.post(f"{BASE_ENDPOINT}{OD_READ_ENDPOINT}", json={"data": None})
    if not bad_reading:
        aioclient_mock.post(
            f"{BASE_ENDPOINT}{LATEST_OD_READ_ENDPOINT}",
            json=load_smt_fixture("latestodrread"),
        )
    else:
        aioclient_mock.post(
            f"{BASE_ENDPOINT}{LATEST_OD_READ_ENDPOINT}",
            json={},
        )


@pytest.fixture(name="config_entry")
def mock_config_entry(hass):
    """Return a mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user123",
        data={"username": "user123", "password": "password123"},
    )
    config_entry.add_to_hass(hass)

    return config_entry
