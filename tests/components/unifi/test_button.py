"""UniFi Network button platform tests."""

from datetime import timedelta

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonDeviceClass
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
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

from .test_hub import setup_unifi_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

WLAN_ID = "_id"
WLAN = {
    WLAN_ID: "012345678910111213141516",
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


async def test_restart_device_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    websocket_mock,
) -> None:
    """Test restarting device button."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[
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
        ],
    )
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 1

    ent_reg_entry = entity_registry.async_get("button.switch_restart")
    assert ent_reg_entry.unique_id == "device_restart-00:00:00:00:01:01"
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Validate state object
    button = hass.states.get("button.switch_restart")
    assert button is not None
    assert button.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    # Send restart device command
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}/cmd/devmgr",
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": "button.switch_restart"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "restart",
        "mac": "00:00:00:00:01:01",
        "reboot_type": "soft",
    }

    # Availability signalling

    # Controller disconnects
    await websocket_mock.disconnect()
    assert hass.states.get("button.switch_restart").state == STATE_UNAVAILABLE

    # Controller reconnects
    await websocket_mock.reconnect()
    assert hass.states.get("button.switch_restart").state != STATE_UNAVAILABLE


async def test_power_cycle_poe(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    websocket_mock,
) -> None:
    """Test restarting device button."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[
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
        ],
    )
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 2

    ent_reg_entry = entity_registry.async_get("button.switch_port_1_power_cycle")
    assert ent_reg_entry.unique_id == "power_cycle-00:00:00:00:01:01_1"
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Validate state object
    button = hass.states.get("button.switch_port_1_power_cycle")
    assert button is not None
    assert button.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    # Send restart device command
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}/cmd/devmgr",
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": "button.switch_port_1_power_cycle"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "cmd": "power-cycle",
        "mac": "00:00:00:00:01:01",
        "port_idx": 1,
    }

    # Availability signalling

    # Controller disconnects
    await websocket_mock.disconnect()
    assert (
        hass.states.get("button.switch_port_1_power_cycle").state == STATE_UNAVAILABLE
    )

    # Controller reconnects
    await websocket_mock.reconnect()
    assert (
        hass.states.get("button.switch_port_1_power_cycle").state != STATE_UNAVAILABLE
    )


async def test_wlan_regenerate_password(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    websocket_mock,
) -> None:
    """Test WLAN regenerate password button."""

    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, wlans_response=[WLAN]
    )
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 0

    button_regenerate_password = "button.ssid_1_regenerate_password"

    ent_reg_entry = entity_registry.async_get(button_regenerate_password)
    assert ent_reg_entry.unique_id == "regenerate_password-012345678910111213141516"
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Enable entity
    entity_registry.async_update_entity(
        entity_id=button_regenerate_password, disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 1

    # Validate state object
    button = hass.states.get(button_regenerate_password)
    assert button is not None
    assert button.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.UPDATE

    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry.data[CONF_SITE_ID]}/rest/wlanconf/{WLAN[WLAN_ID]}",
        json={"data": "password changed successfully", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    # Send WLAN regenerate password command
    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": button_regenerate_password},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert next(iter(aioclient_mock.mock_calls[0][2])) == "x_passphrase"

    # Availability signalling

    # Controller disconnects
    await websocket_mock.disconnect()
    assert hass.states.get(button_regenerate_password).state == STATE_UNAVAILABLE

    # Controller reconnects
    await websocket_mock.reconnect()
    assert hass.states.get(button_regenerate_password).state != STATE_UNAVAILABLE
