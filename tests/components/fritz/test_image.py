"""Tests for Fritz!Tools image platform."""
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import MOCK_FB_SERVICES, MOCK_USER_DATA

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator

GUEST_WIFI_ENABLED: dict[str, dict] = {
    "WLANConfiguration0": {},
    "WLANConfiguration1": {
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewSSID": "GuestWifi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:13",
        },
        "GetSSID": {
            "NewSSID": "GuestWifi",
        },
        "GetSecurityKeys": {"NewKeyPassphrase": "1234567890"},
    },
}

GUEST_WIFI_CHANGED: dict[str, dict] = {
    "WLANConfiguration0": {},
    "WLANConfiguration1": {
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewSSID": "GuestWifi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:13",
        },
        "GetSSID": {
            "NewSSID": "GuestWifi",
        },
        "GetSecurityKeys": {"NewKeyPassphrase": "abcdefghij"},
    },
}

GUEST_WIFI_DISABLED: dict[str, dict] = {
    "WLANConfiguration0": {},
    "WLANConfiguration1": {
        "GetInfo": {
            "NewEnable": False,
            "NewStatus": "Up",
            "NewSSID": "GuestWifi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:13",
        },
        "GetSSID": {
            "NewSSID": "GuestWifi",
        },
        "GetSecurityKeys": {"NewKeyPassphrase": "1234567890"},
    },
}


@pytest.mark.parametrize(
    ("fc_data"),
    [
        ({**MOCK_FB_SERVICES, **GUEST_WIFI_ENABLED}),
        ({**MOCK_FB_SERVICES, **GUEST_WIFI_DISABLED}),
    ],
)
async def test_image_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test image entity."""

    # setup component with image platform only
    with patch(
        "homeassistant.components.fritz.PLATFORMS",
        [Platform.IMAGE],
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
        entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    # test image entity is generated as expected
    states = hass.states.async_all(IMAGE_DOMAIN)
    assert len(states) == 1

    state = states[0]
    assert state.name == "Mock Title GuestWifi"
    assert state.entity_id == "image.mock_title_guestwifi"

    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.mock_title_guestwifi?token={access_token}",
        "friendly_name": "Mock Title GuestWifi",
    }

    entity_registry = async_get_entity_registry(hass)
    entity_entry = entity_registry.async_get("image.mock_title_guestwifi")
    assert entity_entry.unique_id == "1c_ed_6f_12_34_11_guestwifi_qr_code"

    # test image download
    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.mock_title_guestwifi")
    assert resp.status == HTTPStatus.OK

    body = await resp.read()
    assert body == snapshot


@pytest.mark.parametrize(("fc_data"), [({**MOCK_FB_SERVICES, **GUEST_WIFI_ENABLED})])
async def test_image_update(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    fc_class_mock,
    fh_class_mock,
) -> None:
    """Test image update."""

    # setup component with image platform only
    with patch(
        "homeassistant.components.fritz.PLATFORMS",
        [Platform.IMAGE],
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
        entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.mock_title_guestwifi")
    resp_body = await resp.read()
    assert resp.status == HTTPStatus.OK

    fc_class_mock().override_services({**MOCK_FB_SERVICES, **GUEST_WIFI_CHANGED})
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()

    resp = await client.get("/api/image_proxy/image.mock_title_guestwifi")
    resp_body_new = await resp.read()

    assert resp_body != resp_body_new
    assert resp_body_new == snapshot
