"""Tests for Fritz!Tools switch platform."""
from __future__ import annotations

import pytest

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MOCK_FB_SERVICES, MOCK_USER_DATA

from tests.common import MockConfigEntry

MOCK_WLANCONFIGS_SAME_SSID: dict[str, dict] = {
    "WLANConfiguration1": {
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
        }
    },
    "WLANConfiguration2": {
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
        }
    },
}
MOCK_WLANCONFIGS_DIFF_SSID: dict[str, dict] = {
    "WLANConfiguration1": {
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
        }
    },
    "WLANConfiguration2": {
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
        }
    },
}
MOCK_WLANCONFIGS_DIFF2_SSID: dict[str, dict] = {
    "WLANConfiguration1": {
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
        }
    },
    "WLANConfiguration2": {
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
        }
    },
}


@pytest.mark.parametrize(
    "fc_data, expected_wifi_names",
    [
        (
            {**MOCK_FB_SERVICES, **MOCK_WLANCONFIGS_SAME_SSID},
            ["WiFi (2.4Ghz)", "WiFi (5Ghz)"],
        ),
        ({**MOCK_FB_SERVICES, **MOCK_WLANCONFIGS_DIFF_SSID}, ["WiFi", "WiFi2"]),
        (
            {**MOCK_FB_SERVICES, **MOCK_WLANCONFIGS_DIFF2_SSID},
            ["WiFi (2.4Ghz)", "WiFi+ (5Ghz)"],
        ),
    ],
)
async def test_switch_setup(
    hass: HomeAssistant,
    expected_wifi_names: list[str],
    fc_class_mock,
    fh_class_mock,
):
    """Test setup of Fritz!Tools switches."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    switches = hass.states.async_all(Platform.SWITCH)
    assert len(switches) == 3
    assert switches[0].name == f"Mock Title Wi-Fi {expected_wifi_names[0]}"
    assert switches[1].name == f"Mock Title Wi-Fi {expected_wifi_names[1]}"
    assert switches[2].name == "printer Internet Access"
