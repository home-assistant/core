"""UniFi Network button platform tests."""

from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    CONF_HOST,
    CONTENT_TYPE_JSON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
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


@pytest.mark.parametrize("device_payload", [DEVICE_RESTART + DEVICE_POWER_CYCLE_POE])
@pytest.mark.parametrize("wlan_payload", [WLAN_REGENERATE_PASSWORD])
@pytest.mark.parametrize(
    "site_payload",
    [
        [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}],
        [{"desc": "Site name", "name": "site_id", "role": "not admin", "_id": "1"}],
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    site_payload: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data with and without admin rights."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.BUTTON]):
        config_entry = await config_entry_factory()
    if site_payload[0]["role"] == "admin":
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
    else:
        assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 0


async def _test_button_entity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_websocket_state: WebsocketStateManager,
    config_entry: MockConfigEntry,
    entity_id: str,
    request_method: str,
    request_path: str,
    request_data: dict[str, Any],
    call: dict[str, str],
) -> None:
    """Test button entity."""
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
        "entity_id",
        "request_method",
        "request_path",
        "call",
    ),
    [
        (
            DEVICE_RESTART,
            "button.switch_restart",
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
            "button.switch_port_1_power_cycle",
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
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    entity_id: str,
    request_method: str,
    request_path: str,
    call: dict[str, str],
) -> None:
    """Test button entities based on device sources."""
    await _test_button_entity(
        hass,
        aioclient_mock,
        mock_websocket_state,
        config_entry_setup,
        entity_id,
        request_method,
        request_path,
        {},
        call,
    )


@pytest.mark.parametrize(
    (
        "wlan_payload",
        "entity_id",
        "request_method",
        "request_path",
        "request_data",
        "call",
    ),
    [
        (
            WLAN_REGENERATE_PASSWORD,
            "button.ssid_1_regenerate_password",
            "put",
            f"/rest/wlanconf/{WLAN_REGENERATE_PASSWORD[0]['_id']}",
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
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateManager,
    entity_id: str,
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
        aioclient_mock,
        mock_websocket_state,
        config_entry_setup,
        entity_id,
        request_method,
        request_path,
        request_data,
        call,
    )


@pytest.mark.parametrize("device_payload", [DEVICE_POWER_CYCLE_POE])
@pytest.mark.usefixtures("config_entry_setup")
async def test_power_cycle_availability(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: dict[str, Any],
) -> None:
    """Verify that disabling PoE marks entity as unavailable."""
    entity_id = "button.switch_port_1_power_cycle"

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # PoE disabled

    device_1 = deepcopy(device_payload[0])
    device_1["port_table"][0]["poe_enable"] = False
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # PoE enabled
    device_1 = deepcopy(device_payload[0])
    device_1["port_table"][0]["poe_enable"] = True
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
