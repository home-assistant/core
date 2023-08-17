"""Fixtures for the Yale Smart Living integration."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from yalesmartalarmclient.const import YALE_STATE_ARM_FULL

from homeassistant.components.yale_smart_alarm.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

ENTRY_CONFIG = {
    "username": "test-username",
    "password": "new-test-password",
    "name": "Yale Smart Alarm",
    "area_id": "1",
}
OPTIONS_CONFIG = {"lock_code_digits": 6}


@pytest.fixture
async def load_int(hass: HomeAssistant, load_json: dict[str, Any]) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        unique_id="username",
        version=1,
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.yale_smart_alarm.coordinator.YaleSmartAlarmClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.auth = None
        client.lock_api = None
        client.get_all.return_value = load_json
        client.get_armed_status.return_value = YALE_STATE_ARM_FULL
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="load_json", scope="session")
def load_json_from_fixture() -> dict[str, Any]:
    """Load fixture with json data and return."""

    data_fixture = load_fixture("get_all.json", "yale_smart_alarm")
    json_data: dict[str, Any] = json.loads(data_fixture)
    return json_data
