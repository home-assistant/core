"""Tests for Fritz!Tools switch platform."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from fritzconnection.core.exceptions import FritzActionError
from fritzconnection.lib.fritzstatus import DefaultConnectionService
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fritz import switch as fritz_switch
from homeassistant.components.fritz.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import slugify

from .conftest import FritzConnectionMock, wifi_services_with_ssids
from .const import (
    MOCK_CALL_DEFLECTION_DATA,
    MOCK_FB_SERVICES,
    MOCK_HOST_ATTRIBUTES_DATA,
    MOCK_MESH_MASTER_MAC,
    MOCK_USER_DATA,
)

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


async def test_switch_no_device_conn_type(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches when no device connection type is available."""

    entity_id = "switch.mock_title_port_forward_test_port_mapping"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    fs_class_mock.get_default_connection_service.return_value = (
        DefaultConnectionService("", "", "")
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id) is None


async def test_switch_empty_port_entities_list(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches with empty port entities."""

    entity_id = "switch.mock_title_port_forward_test_port_mapping"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_get_num_port_mapping",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id) is None


async def test_switch_no_port_entities_list(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches with no port entities."""

    entity_id = "switch.mock_title_port_forward_test_port_mapping"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.AvmWrapper.async_get_port_mapping",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id) is None


async def test_switch_no_profile_entities_list(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches with no profile entities."""

    entity_id = "switch.printer_internet_access"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    services = deepcopy(MOCK_FB_SERVICES)
    services.pop("X_AVM-DE_HostFilter1")
    fc_class_mock.return_value = FritzConnectionMock(services)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id) is None


async def test_switch_no_mesh_wifi_uplink(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches when no mesh WiFi uplink."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    fh_class_mock.get_mesh_topology.side_effect = FritzActionError(
        "No mesh WiFi uplink"
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_switch_device_no_wan_access(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches when device has no WAN access."""

    entity_id = "switch.printer_internet_access"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    attributes = [
        {k: v for k, v in host.items() if k != "X_AVM-DE_WANAccess"}
        for host in MOCK_HOST_ATTRIBUTES_DATA
    ]
    fh_class_mock.get_hosts_attributes = MagicMock(return_value=attributes)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_switch_device_no_ip_address(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
) -> None:
    """Test Fritz!Tools switches when device has no IP address."""

    entity_id = "switch.printer_internet_access"

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    attributes = deepcopy(MOCK_HOST_ATTRIBUTES_DATA)
    attributes[0]["IPAddress"] = ""

    fh_class_mock.get_hosts_attributes = MagicMock(return_value=attributes)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("entity_id", "wrapper_method", "state_value"),
    [
        (
            "switch.mock_title_port_forward_test_port_mapping",
            "async_add_port_mapping",
            STATE_OFF,
        ),
        (
            "switch.printer_internet_access",
            "async_set_allow_wan_access",
            STATE_ON,
        ),
        (
            "switch.mock_title_call_deflection_0",
            "async_set_deflection_enable",
            STATE_ON,
        ),
        (
            "switch.mock_title_wi_fi_guest",
            "async_set_wlan_configuration",
            STATE_ON,
        ),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    entity_id: str,
    wrapper_method: str,
    state_value: str,
) -> None:
    """Test Fritz!Tools switches turn on and turn off."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    fc_class_mock.return_value = FritzConnectionMock(
        MOCK_FB_SERVICES | MOCK_CALL_DEFLECTION_DATA
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    with patch(
        f"homeassistant.components.fritz.coordinator.AvmWrapper.{wrapper_method}",
    ) as mock_set_action:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_set_action.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF

    with patch(
        f"homeassistant.components.fritz.coordinator.AvmWrapper.{wrapper_method}",
    ) as mock_set_action_2:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_set_action_2.assert_called_once()

    assert (state := hass.states.get(entity_id))
    assert state.state == state_value


@pytest.mark.parametrize(
    ("ssid_1", "ssid_2", "old_descriptions", "new_identifiers"),
    [
        (
            "Main WiFi / +",
            "Guest WiFi / +",
            [
                "Wi-Fi Main WiFi / +",
                "Wi-Fi Guest WiFi / +",
            ],
            ["main_2_4ghz", "guest"],
        ),
        (
            "My WiFi / +",
            "My WiFi / +",
            [
                "Wi-Fi My WiFi / + (2.4Ghz)",
                "Wi-Fi My WiFi / + (5Ghz)",
            ],
            ["main_2_4ghz", "guest"],
        ),
    ],
)
async def test_migrate_to_new_unique_id(
    hass: HomeAssistant,
    fc_class_mock,
    fh_class_mock,
    fs_class_mock,
    entity_registry: EntityRegistry,
    device_registry: dr.DeviceRegistry,
    ssid_1: str,
    ssid_2: str,
    old_descriptions: list[str],
    new_identifiers: list[str],
) -> None:
    """Test migrate from old unique ids to new unique ids."""

    MOCK_UNIQUE_ID = "1234567890"

    fc_class_mock.return_value.override_services(
        wifi_services_with_ssids(ssid_1, ssid_2)
    )

    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_USER_DATA, unique_id=MOCK_UNIQUE_ID
    )
    entry.add_to_hass(hass)

    entity_ids: list[str] = []
    old_unique_ids: list[str] = []
    new_unique_ids: list[str] = []
    for old_description, new_identifier in zip(
        old_descriptions, new_identifiers, strict=True
    ):
        old_unique_id = f"{MOCK_MESH_MASTER_MAC}-{slugify(old_description)}"
        new_unique_id = f"{MOCK_MESH_MASTER_MAC}-wi_fi_{new_identifier}"
        old_unique_ids.append(old_unique_id)
        new_unique_ids.append(new_unique_id)
        entity_ids.append(f"switch.fritz_{slugify(old_unique_id)}")

        entity_registry.async_get_or_create(
            disabled_by=None,
            domain=SWITCH_DOMAIN,
            platform=DOMAIN,
            unique_id=old_unique_id,
            config_entry=entry,
        )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_UNIQUE_ID)},
        connections={
            (dr.CONNECTION_NETWORK_MAC, MOCK_MESH_MASTER_MAC),
        },
    )
    await hass.async_block_till_done()

    for entity_id, old_unique_id in zip(entity_ids, old_unique_ids, strict=True):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.unique_id == old_unique_id

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for entity_id, new_unique_id in zip(entity_ids, new_unique_ids, strict=True):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.unique_id == new_unique_id


async def test_wifi_naming_internal_comm_and_skipped() -> None:
    """Test skip internal Wi-Fi network."""
    # Prepare AvmWrapper mock with 4 Wi-Fi networks
    avm_wrapper = MagicMock()
    avm_wrapper.connection.services = [
        "WLANConfiguration1",
        "WLANConfiguration2",
        "WLANConfiguration3",
        "WLANConfiguration4",
    ]
    # The 3rd network (index 2) should be skipped
    wifi_configs = [
        {"NewSSID": "wifi1"},
        {"NewSSID": "wifi2"},
        {"NewSSID": "wifi3"},
        {"NewSSID": "wifi4"},
    ]
    avm_wrapper.async_get_wlan_configuration = AsyncMock(side_effect=wifi_configs)

    networks = await fritz_switch._get_wifi_networks_list(avm_wrapper)
    # The 3rd network (index 2) should be skipped
    assert 3 not in networks  # 1-based index, so 3 is the 3rd
    # The rest should be present
    assert set(networks.keys()) == {1, 2, 4}


@pytest.mark.parametrize(
    ("wifi_index", "wifi_count", "expected_name"),
    [
        (0, 2, "Main 2.4Ghz"),
        (1, 3, "Main 5Ghz"),
        (1, 2, "Guest"),
        (2, 4, None),
        (2, 5, None),
    ],
)
def test_wifi_naming_helper(
    wifi_index: int, wifi_count: int, expected_name: str | None
) -> None:
    """Test Wi-Fi naming helper covers supported and fallback branches."""
    assert fritz_switch._wifi_naming({}, wifi_index, wifi_count) == expected_name
