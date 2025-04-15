"""Tests for Fritz!Tools switch platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import MOCK_CALL_DEFLECTION_DATA, MOCK_FB_SERVICES, MOCK_USER_DATA

from tests.common import MockConfigEntry, snapshot_platform

MOCK_WLANCONFIGS_SAME_SSID: dict[str, dict] = {
    "WLANConfiguration1": {
        "GetSSID": {"NewSSID": "WiFi"},
        "GetSecurityKeys": {"NewKeyPassphrase": "mysecret"},
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": 13,
            "NewSSID": "WiFi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": False,
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:12",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
        },
    },
    "WLANConfiguration2": {
        "GetSSID": {"NewSSID": "WiFi"},
        "GetSecurityKeys": {"NewKeyPassphrase": "mysecret"},
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": 52,
            "NewSSID": "WiFi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": False,
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:13",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
        },
    },
}
MOCK_WLANCONFIGS_DIFF_SSID: dict[str, dict] = {
    "WLANConfiguration1": {
        "GetSSID": {"NewSSID": "WiFi"},
        "GetSecurityKeys": {"NewKeyPassphrase": "mysecret"},
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": 13,
            "NewSSID": "WiFi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": False,
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:12",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
        },
    },
    "WLANConfiguration2": {
        "GetSSID": {"NewSSID": "WiFi2"},
        "GetSecurityKeys": {"NewKeyPassphrase": "mysecret"},
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": 52,
            "NewSSID": "WiFi2",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": False,
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:13",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
        },
    },
}
MOCK_WLANCONFIGS_DIFF2_SSID: dict[str, dict] = {
    "WLANConfiguration1": {
        "GetSSID": {"NewSSID": "WiFi"},
        "GetSecurityKeys": {"NewKeyPassphrase": "mysecret"},
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": 13,
            "NewSSID": "WiFi",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": False,
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:12",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
        },
    },
    "WLANConfiguration2": {
        "GetSSID": {"NewSSID": "WiFi+"},
        "GetSecurityKeys": {"NewKeyPassphrase": "mysecret"},
        "GetInfo": {
            "NewEnable": True,
            "NewStatus": "Up",
            "NewMaxBitRate": "Auto",
            "NewChannel": 52,
            "NewSSID": "WiFi+",
            "NewBeaconType": "11iandWPA3",
            "NewX_AVM-DE_PossibleBeaconTypes": "None,11i,11iandWPA3",
            "NewMACAddressControlEnabled": False,
            "NewStandard": "ax",
            "NewBSSID": "1C:ED:6F:12:34:13",
            "NewBasicEncryptionModes": "None",
            "NewBasicAuthenticationMode": "None",
            "NewMaxCharsSSID": 32,
            "NewMinCharsSSID": 1,
            "NewAllowedCharsSSID": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
            "NewMinCharsPSK": 64,
            "NewMaxCharsPSK": 64,
            "NewAllowedCharsPSK": "0123456789ABCDEFabcdef",
        },
    },
}


@pytest.mark.parametrize(
    ("fc_data"),
    [
        ({**MOCK_FB_SERVICES, **MOCK_WLANCONFIGS_SAME_SSID}),
        ({**MOCK_FB_SERVICES, **MOCK_WLANCONFIGS_DIFF_SSID}),
        ({**MOCK_FB_SERVICES, **MOCK_WLANCONFIGS_DIFF2_SSID}),
        ({**MOCK_FB_SERVICES, **MOCK_CALL_DEFLECTION_DATA}),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    fc_class_mock,
    fh_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup of Fritz!Tools switches."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fritz.PLATFORMS", [Platform.SWITCH]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
