"""The tests for nuki integration."""

import requests_mock

from homeassistant.components.nuki.const import DOMAIN
from homeassistant.core import HomeAssistant

from .mock import MOCK_INFO, setup_nuki_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)


async def init_integration(
    hass: HomeAssistant, mock_nuki_requests: requests_mock.Mocker
) -> MockConfigEntry:
    """Mock integration setup."""
    # Mocking authentication endpoint
    mock_nuki_requests.get("http://1.1.1.1:8080/info", json=MOCK_INFO)
    mock_nuki_requests.get(
        "http://1.1.1.1:8080/list",
        json=await async_load_json_array_fixture(hass, "list.json", DOMAIN),
    )
    callback_list_data = await async_load_json_object_fixture(
        hass, "callback_list.json", DOMAIN
    )
    mock_nuki_requests.get(
        "http://1.1.1.1:8080/callback/list",
        json=callback_list_data,
    )
    mock_nuki_requests.get(
        "http://1.1.1.1:8080/callback/add",
        json=await async_load_json_object_fixture(hass, "callback_add.json", DOMAIN),
    )
    # Mock the callback remove endpoint for teardown
    mock_nuki_requests.delete(
        requests_mock.ANY,
        json={"success": True},
    )
    entry = await setup_nuki_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
