"""Tests for the sensors provided by the Roku integration."""
from unittest.mock import MagicMock

import pytest
from rokuecp import Device as RokuDevice

from homeassistant.components.binary_sensor import STATE_OFF, STATE_ON
from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry
from tests.components.roku import UPNP_SERIAL


async def test_roku_binary_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the Roku binary sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("binary_sensor.my_roku_3_headphones_connected")
    entry = entity_registry.async_get("binary_sensor.my_roku_3_headphones_connected")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_headphones_connected"
    assert entry.entity_category is None
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Headphones connected"
    assert state.attributes.get(ATTR_ICON) == "mdi:headphones"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.my_roku_3_supports_airplay")
    entry = entity_registry.async_get("binary_sensor.my_roku_3_supports_airplay")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_supports_airplay"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Supports AirPlay"
    assert state.attributes.get(ATTR_ICON) == "mdi:cast-variant"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.my_roku_3_supports_ethernet")
    entry = entity_registry.async_get("binary_sensor.my_roku_3_supports_ethernet")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_supports_ethernet"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Supports ethernet"
    assert state.attributes.get(ATTR_ICON) == "mdi:ethernet"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.my_roku_3_supports_find_remote")
    entry = entity_registry.async_get("binary_sensor.my_roku_3_supports_find_remote")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_supports_find_remote"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Supports find remote"
    assert state.attributes.get(ATTR_ICON) == "mdi:remote"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, UPNP_SERIAL)}
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "b0:a7:37:96:4d:fb"),
        (dr.CONNECTION_NETWORK_MAC, "b0:a7:37:96:4d:fa"),
    }
    assert device_entry.manufacturer == "Roku"
    assert device_entry.model == "Roku 3"
    assert device_entry.name == "My Roku 3"
    assert device_entry.entry_type is None
    assert device_entry.sw_version == "7.5.0"
    assert device_entry.hw_version == "4200X"
    assert device_entry.suggested_area is None


@pytest.mark.parametrize("mock_device", ["roku/rokutv-7820x.json"], indirect=True)
async def test_rokutv_binary_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_device: RokuDevice,
    mock_roku: MagicMock,
) -> None:
    """Test the Roku binary sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("binary_sensor.58_onn_roku_tv_headphones_connected")
    entry = entity_registry.async_get(
        "binary_sensor.58_onn_roku_tv_headphones_connected"
    )
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_headphones_connected"
    assert entry.entity_category is None
    assert state.state == STATE_OFF
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == '58" Onn Roku TV Headphones connected'
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:headphones"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.58_onn_roku_tv_supports_airplay")
    entry = entity_registry.async_get("binary_sensor.58_onn_roku_tv_supports_airplay")
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_supports_airplay"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_ON
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == '58" Onn Roku TV Supports AirPlay'
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:cast-variant"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.58_onn_roku_tv_supports_ethernet")
    entry = entity_registry.async_get("binary_sensor.58_onn_roku_tv_supports_ethernet")
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_supports_ethernet"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_ON
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == '58" Onn Roku TV Supports ethernet'
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:ethernet"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.58_onn_roku_tv_supports_find_remote")
    entry = entity_registry.async_get(
        "binary_sensor.58_onn_roku_tv_supports_find_remote"
    )
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_supports_find_remote"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_ON
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == '58" Onn Roku TV Supports find remote'
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:remote"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "YN00H5555555")}
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "d8:13:99:f8:b0:c6"),
        (dr.CONNECTION_NETWORK_MAC, "d4:3a:2e:07:fd:cb"),
    }
    assert device_entry.manufacturer == "Onn"
    assert device_entry.model == "100005844"
    assert device_entry.name == '58" Onn Roku TV'
    assert device_entry.entry_type is None
    assert device_entry.sw_version == "9.2.0"
    assert device_entry.hw_version == "7820X"
    assert device_entry.suggested_area == "Living room"
