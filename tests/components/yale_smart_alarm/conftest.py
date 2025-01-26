"""Fixtures for the Yale Smart Living integration."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
from yalesmartalarmclient import YaleDoorManAPI, YaleLock, YaleSmartAlarmData
from yalesmartalarmclient.const import YALE_STATE_ARM_FULL

from homeassistant.components.yale_smart_alarm.const import DOMAIN, PLATFORMS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

ENTRY_CONFIG = {
    "username": "test-username",
    "password": "new-test-password",
    "area_id": "1",
}
OPTIONS_CONFIG = {"lock_code_digits": 6}


@pytest.fixture(name="load_platforms")
async def patch_platform_constant() -> list[Platform]:
    """Return list of platforms to load."""
    return PLATFORMS


@pytest.fixture
async def load_config_entry(
    hass: HomeAssistant,
    get_client: Mock,
    load_platforms: list[Platform],
) -> tuple[MockConfigEntry, Mock]:
    """Set up the Yale Smart Living integration in Home Assistant."""
    with patch("homeassistant.components.yale_smart_alarm.PLATFORMS", load_platforms):
        config_entry = MockConfigEntry(
            title=ENTRY_CONFIG["username"],
            domain=DOMAIN,
            source=SOURCE_USER,
            data=ENTRY_CONFIG,
            options=OPTIONS_CONFIG,
            entry_id="1",
            unique_id="username",
            version=2,
            minor_version=2,
        )

        config_entry.add_to_hass(hass)
        with patch(
            "homeassistant.components.yale_smart_alarm.coordinator.YaleSmartAlarmClient",
            return_value=get_client,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        return (config_entry, get_client)


@pytest.fixture(name="get_client")
async def mock_client(
    get_data: YaleSmartAlarmData,
    get_all_data: YaleSmartAlarmData,
) -> Mock:
    """Mock the Yale client."""
    cycle = get_data.cycle["data"]
    data = {"data": cycle["device_status"]}

    with patch(
        "homeassistant.components.yale_smart_alarm.coordinator.YaleSmartAlarmClient",
        autospec=True,
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.auth = Mock()
        client.auth.get_authenticated = Mock(return_value=data)
        client.auth.post_authenticated = Mock(return_value={"code": "000"})
        client.auth.put_authenticated = Mock(return_value={"code": "000"})
        client.lock_api = YaleDoorManAPI(client.auth)
        locks = [
            YaleLock(device, lock_api=client.lock_api)
            for device in cycle["device_status"]
            if device["type"] == YaleLock.DEVICE_TYPE
        ]
        client.get_locks.return_value = locks
        client.get_all.return_value = get_all_data
        client.get_information.return_value = get_data
        client.get_armed_status.return_value = YALE_STATE_ARM_FULL

        return client


@pytest.fixture(name="loaded_fixture", scope="package")
def get_fixture_data() -> dict[str, Any]:
    """Load fixture with json data and return."""

    data_fixture = load_fixture("get_all.json", "yale_smart_alarm")
    json_data: dict[str, Any] = json.loads(data_fixture)
    return json_data


@pytest.fixture(name="get_data")
def get_update_data(loaded_fixture: dict[str, Any]) -> YaleSmartAlarmData:
    """Load update data and return."""

    status = {"data": loaded_fixture["STATUS"]}
    cycle = {"data": loaded_fixture["CYCLE"]}
    online = {"data": loaded_fixture["ONLINE"]}
    panel_info = {"data": loaded_fixture["PANEL INFO"]}
    return YaleSmartAlarmData(
        status=status,
        cycle=cycle,
        online=online,
        panel_info=panel_info,
    )


@pytest.fixture(name="get_all_data")
def get_diag_data(loaded_fixture: dict[str, Any]) -> YaleSmartAlarmData:
    """Load all data and return."""

    devices = {"data": loaded_fixture["DEVICES"]}
    mode = {"data": loaded_fixture["MODE"]}
    status = {"data": loaded_fixture["STATUS"]}
    cycle = {"data": loaded_fixture["CYCLE"]}
    online = {"data": loaded_fixture["ONLINE"]}
    history = {"data": loaded_fixture["HISTORY"]}
    panel_info = {"data": loaded_fixture["PANEL INFO"]}
    auth_check = {"data": loaded_fixture["AUTH CHECK"]}
    return YaleSmartAlarmData(
        devices=devices,
        mode=mode,
        status=status,
        cycle=cycle,
        online=online,
        history=history,
        panel_info=panel_info,
        auth_check=auth_check,
    )
