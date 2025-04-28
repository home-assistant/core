"""UniFi Network image platform tests."""

from copy import deepcopy
from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def mock_getrandbits():
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


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


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.parametrize(
    "site_payload",
    [
        [{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}],
        [{"desc": "Site name", "name": "site_id", "role": "not admin", "_id": "1"}],
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2021-01-01 01:01:00")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    site_payload: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data with and without admin rights."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.IMAGE]):
        config_entry = await config_entry_factory()
    if site_payload[0]["role"] == "admin":
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
    else:
        assert len(hass.states.async_entity_ids(IMAGE_DOMAIN)) == 0


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_wlan_qr_code(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_websocket_message: WebsocketMessageMock,
) -> None:
    """Test the update_clients function when no clients are found."""
    assert len(hass.states.async_entity_ids(IMAGE_DOMAIN)) == 0

    ent_reg_entry = entity_registry.async_get("image.ssid_1_qr_code")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(
        entity_id="image.ssid_1_qr_code", disabled_by=None
    )
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate image
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.ssid_1_qr_code")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == snapshot

    # Update state object - same password - no change to state
    image_state_1 = hass.states.get("image.ssid_1_qr_code")
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=WLAN)
    image_state_2 = hass.states.get("image.ssid_1_qr_code")
    assert image_state_1.state == image_state_2.state

    # Update state object - changed password - new state
    data = deepcopy(WLAN)
    data["x_passphrase"] = "new password"
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=data)
    image_state_3 = hass.states.get("image.ssid_1_qr_code")
    assert image_state_1.state != image_state_3.state

    # Validate image
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.ssid_1_qr_code")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == snapshot


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hub_state_change(
    hass: HomeAssistant, mock_websocket_state: WebsocketStateManager
) -> None:
    """Verify entities state reflect on hub becoming unavailable."""
    assert hass.states.get("image.ssid_1_qr_code").state != STATE_UNAVAILABLE

    # Controller unavailable
    await mock_websocket_state.disconnect()
    assert hass.states.get("image.ssid_1_qr_code").state == STATE_UNAVAILABLE

    # Controller available
    await mock_websocket_state.reconnect()
    assert hass.states.get("image.ssid_1_qr_code").state != STATE_UNAVAILABLE


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_source_availability(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Verify entities state reflect on source becoming unavailable."""
    assert hass.states.get("image.ssid_1_qr_code").state != STATE_UNAVAILABLE

    # WLAN gets disabled
    wlan_1 = deepcopy(WLAN)
    wlan_1["enabled"] = False
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    assert hass.states.get("image.ssid_1_qr_code").state == STATE_UNAVAILABLE

    # WLAN gets re-enabled
    wlan_1["enabled"] = True
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    assert hass.states.get("image.ssid_1_qr_code").state != STATE_UNAVAILABLE
