"""UniFi Network image platform tests."""

from copy import deepcopy
from datetime import timedelta
from http import HTTPStatus

from aiounifi.models.message import MessageKey
from aiounifi.websocket import WebsocketState
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

from .test_controller import (
    setup_unifi_integration,
)

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

WLAN = {
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


async def test_wlan_qr_code(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_unifi_websocket,
) -> None:
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(hass, aioclient_mock, wlans_response=[WLAN])
    assert len(hass.states.async_entity_ids(IMAGE_DOMAIN)) == 0

    ent_reg = er.async_get(hass)
    ent_reg_entry = ent_reg.async_get("image.ssid_1_qr_code")
    assert ent_reg_entry.unique_id == "qr_code-012345678910111213141516"
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    # Enable entity
    ent_reg.async_update_entity(entity_id="image.ssid_1_qr_code", disabled_by=None)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate state object
    image_state_1 = hass.states.get("image.ssid_1_qr_code")
    assert image_state_1.name == "SSID 1 QR Code"

    # Validate image
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.ssid_1_qr_code")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == snapshot

    # Update state object - same password - no change to state
    mock_unifi_websocket(message=MessageKey.WLAN_CONF_UPDATED, data=WLAN)
    await hass.async_block_till_done()
    image_state_2 = hass.states.get("image.ssid_1_qr_code")
    assert image_state_1.state == image_state_2.state

    # Update state object - changed password - new state
    data = deepcopy(WLAN)
    data["x_passphrase"] = "new password"
    mock_unifi_websocket(message=MessageKey.WLAN_CONF_UPDATED, data=data)
    await hass.async_block_till_done()
    image_state_3 = hass.states.get("image.ssid_1_qr_code")
    assert image_state_1.state != image_state_3.state

    # Validate image
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.ssid_1_qr_code")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == snapshot

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get("image.ssid_1_qr_code").state == STATE_UNAVAILABLE

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("image.ssid_1_qr_code").state != STATE_UNAVAILABLE

    # WLAN gets disabled
    wlan_1 = deepcopy(WLAN)
    wlan_1["enabled"] = False
    mock_unifi_websocket(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    await hass.async_block_till_done()
    assert hass.states.get("image.ssid_1_qr_code").state == STATE_UNAVAILABLE

    # WLAN gets re-enabled
    wlan_1["enabled"] = True
    mock_unifi_websocket(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    await hass.async_block_till_done()
    assert hass.states.get("image.ssid_1_qr_code").state != STATE_UNAVAILABLE
