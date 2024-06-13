"""UniFi Network button platform tests."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonDeviceClass
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_HOST,
    CONTENT_TYPE_JSON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

RANDOM_TOKEN = "random_token"


@pytest.fixture(autouse=True)
def mock_secret():
    """Mock secret."""
    with patch("secrets.token_urlsafe", return_value=RANDOM_TOKEN):
        yield


DEVICE_RESTART = [
    {
        "board_rev": 3,
        "device_id": "mock-id",
        "ip": "10.0.0.1",
        "last_seen": 1562600145,
        "mac": "00:00:00:00:01:01",
        "model": "US16P150",
        "name": "switch",
        "state": 1,
        "type": "usw",
        "version": "4.0.42.10433",
    }
]

DEVICE_POWER_CYCLE_POE = [
    {
        "board_rev": 3,
        "device_id": "mock-id",
        "ip": "10.0.0.1",
        "last_seen": 1562600145,
        "mac": "00:00:00:00:01:01",
        "model": "US16P150",
        "name": "switch",
        "state": 1,
        "type": "usw",
        "version": "4.0.42.10433",
        "port_table": [
            {
                "media": "GE",
                "name": "Port 1",
                "port_idx": 1,
                "poe_caps": 7,
                "poe_class": "Class 4",
                "poe_enable": True,
                "poe_mode": "auto",
                "poe_power": "2.56",
                "poe_voltage": "53.40",
                "portconf_id": "1a1",
                "port_poe": True,
                "up": True,
            },
        ],
    }
]

WLAN_REGENERATE_PASSWORD = [
    {
        "_id": "012345678910111213141516",
        "bc_filter_enabled": False,
        "bc_filter_list": [],
        "dtim_mode": "default",
        "dtim_na": 1,
        "dtim_ng": 1,
        "enabled": True,
        "group_rekey": 3600,
        "mac_filter_enabled": False,
        "mac_filter_list": [],
        "mac_filter_policy": "allow",
        "minrate_na_advertising_rates": False,
        "minrate_na_beacon_rate_kbps": 6000,
        "minrate_na_data_rate_kbps": 6000,
        "minrate_na_enabled": False,
        "minrate_na_mgmt_rate_kbps": 6000,
        "minrate_ng_advertising_rates": False,
        "minrate_ng_beacon_rate_kbps": 1000,
        "minrate_ng_data_rate_kbps": 1000,
        "minrate_ng_enabled": False,
        "minrate_ng_mgmt_rate_kbps": 1000,
        "name": "SSID 1",
        "no2ghz_oui": False,
        "schedule": [],
        "security": "wpapsk",
        "site_id": "5a32aa4ee4b0412345678910",
        "usergroup_id": "012345678910111213141518",
        "wep_idx": 1,
        "wlangroup_id": "012345678910111213141519",
        "wpa_enc": "ccmp",
        "wpa_mode": "wpa2",
        "x_iapp_key": "01234567891011121314151617181920",
        "x_passphrase": "password",
    }
]


async def _test_button_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    mock_websocket_state,
    config_entry: ConfigEntry,
    entity_count: int,
    entity_id: str,
    unique_id: str,
    device_class: ButtonDeviceClass,
    request_method: str,
    request_path: str,
    request_data: dict[str, Any],
    call: dict[str, str],
) -> None:
    """Test button entity."""
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == entity_count

    ent_reg_entry = entity_registry.async_get(entity_id)
    assert ent_reg_entry.unique_id == unique_id
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Validate state object
    button = hass.states.get(entity_id)
    assert button is not None
    assert button.attributes.get(ATTR_DEVICE_CLASS) == device_class

    # Send and validate device command
    aioclient_mock.clear_requests()
    aioclient_mock.request(
        request_method,
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}{request_path}",
        **request_data,
    )

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {"entity_id": entity_id}, blocking=True
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == call

    # Availability signalling

    # Controller disconnects
    await mock_websocket_state.disconnect()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Controller reconnects
    await mock_websocket_state.reconnect()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    (
        "device_payload",
        "entity_count",
        "entity_id",
        "unique_id",
        "device_class",
        "request_method",
        "request_path",
        "call",
    ),
    [
        (
            DEVICE_RESTART,
            1,
            "button.switch_restart",
            "device_restart-00:00:00:00:01:01",
            ButtonDeviceClass.RESTART,
            "post",
            "/cmd/devmgr",
            {
                "cmd": "restart",
                "mac": "00:00:00:00:01:01",
                "reboot_type": "soft",
            },
        ),
        (
            DEVICE_POWER_CYCLE_POE,
            2,
            "button.switch_port_1_power_cycle",
            "power_cycle-00:00:00:00:01:01_1",
            ButtonDeviceClass.RESTART,
            "post",
            "/cmd/devmgr",
            {
                "cmd": "power-cycle",
                "mac": "00:00:00:00:01:01",
                "port_idx": 1,
            },
        ),
    ],
)
async def test_device_button_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
    mock_websocket_state,
    entity_count: int,
    entity_id: str,
    unique_id: str,
    device_class: ButtonDeviceClass,
    request_method: str,
    request_path: str,
    call: dict[str, str],
) -> None:
    """Test button entities based on device sources."""
    await _test_button_entity(
        hass,
        entity_registry,
        aioclient_mock,
        mock_websocket_state,
        config_entry_setup,
        entity_count,
        entity_id,
        unique_id,
        device_class,
        request_method,
        request_path,
        {},
        call,
    )


@pytest.mark.parametrize(
    (
        "wlan_payload",
        "entity_count",
        "entity_id",
        "unique_id",
        "device_class",
        "request_method",
        "request_path",
        "request_data",
        "call",
    ),
    [
        (
            WLAN_REGENERATE_PASSWORD,
            1,
            "button.ssid_1_regenerate_password",
            "regenerate_password-012345678910111213141516",
            ButtonDeviceClass.UPDATE,
            "put",
            f"/rest/wlanconf/{WLAN_REGENERATE_PASSWORD[0]["_id"]}",
            {
                "json": {"data": "password changed successfully", "meta": {"rc": "ok"}},
                "headers": {"content-type": CONTENT_TYPE_JSON},
            },
            {"x_passphrase": RANDOM_TOKEN},
        ),
    ],
)
async def test_wlan_button_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
    mock_websocket_state,
    entity_count: int,
    entity_id: str,
    unique_id: str,
    device_class: ButtonDeviceClass,
    request_method: str,
    request_path: str,
    request_data: dict[str, Any],
    call: dict[str, str],
) -> None:
    """Test button entities based on WLAN sources."""
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 0

    ent_reg_entry = entity_registry.async_get(entity_id)
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    await _test_button_entity(
        hass,
        entity_registry,
        aioclient_mock,
        mock_websocket_state,
        config_entry_setup,
        entity_count,
        entity_id,
        unique_id,
        device_class,
        request_method,
        request_path,
        request_data,
        call,
    )
