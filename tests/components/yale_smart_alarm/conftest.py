"""Fixtures for the Yale Smart Living integration."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
from yalesmartalarmclient.const import YALE_STATE_ARM_FULL

from homeassistant.components.yale_smart_alarm.const import DOMAIN, PLATFORMS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

ENTRY_CONFIG = {
    "username": "test-username",
    "password": "new-test-password",
    "name": "Yale Smart Alarm",
    "area_id": "1",
}
OPTIONS_CONFIG = {"lock_code_digits": 6}


@pytest.fixture(name="load_platforms")
async def patch_platform_constant() -> list[Platform]:
    """Return list of platforms to load."""
    return PLATFORMS


@pytest.fixture
async def load_config_entry(
    hass: HomeAssistant, load_json: dict[str, Any], load_platforms: list[Platform]
) -> tuple[MockConfigEntry, Mock]:
    """Set up the Yale Smart Living integration in Home Assistant."""
    with patch("homeassistant.components.yale_smart_alarm.PLATFORMS", load_platforms):
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
            client.auth = Mock()
            client.lock_api = Mock()
            client.get_all.return_value = load_json
            client.get_armed_status.return_value = YALE_STATE_ARM_FULL
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        return (config_entry, client)


@pytest.fixture(name="load_json", scope="package")
def load_json_from_fixture() -> dict[str, Any]:
    """Load fixture with json data and return."""

    data_fixture = load_fixture("get_all.json", "yale_smart_alarm")
    json_data: dict[str, Any] = json.loads(data_fixture)
    return json_data
