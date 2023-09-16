"""Tests for the sensors provided by the Roku integration."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import UPNP_SERIAL

from tests.common import MockConfigEntry


async def test_roku_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Roku sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.my_roku_3_active_app")
    entry = entity_registry.async_get("sensor.my_roku_3_active_app")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_active_app"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "Roku"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Active app"
    assert state.attributes.get(ATTR_ICON) == "mdi:application"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.my_roku_3_active_app_id")
    entry = entity_registry.async_get("sensor.my_roku_3_active_app_id")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_active_app_id"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Active app ID"
    assert state.attributes.get(ATTR_ICON) == "mdi:application-cog"
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
async def test_rokutv_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_roku: MagicMock,
) -> None:
    """Test the Roku TV sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.58_onn_roku_tv_active_app")
    entry = entity_registry.async_get("sensor.58_onn_roku_tv_active_app")
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_active_app"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "Antenna TV"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == '58" Onn Roku TV Active app'
    assert state.attributes.get(ATTR_ICON) == "mdi:application"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.58_onn_roku_tv_active_app_id")
    entry = entity_registry.async_get("sensor.58_onn_roku_tv_active_app_id")
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_active_app_id"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "tvinput.dtv"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == '58" Onn Roku TV Active app ID'
    assert state.attributes.get(ATTR_ICON) == "mdi:application-cog"
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
