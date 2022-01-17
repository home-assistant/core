"""Tests for the sensors provided by the Roku integration."""
from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.components.roku import UPNP_SERIAL, setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_roku_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Roku sensors."""
    await setup_integration(hass, aioclient_mock)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.my_roku_3_active_app")
    entry = entity_registry.async_get("sensor.my_roku_3_active_app")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_active_app"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "Roku"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Active App"
    assert state.attributes.get(ATTR_ICON) == "mdi:application"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.my_roku_3_active_app_id")
    entry = entity_registry.async_get("sensor.my_roku_3_active_app_id")
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_active_app_id"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Roku 3 Active App ID"
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


async def test_rokutv_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Roku TV sensors."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host="192.168.1.161",
        unique_id="YN00H5555555",
    )

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.58_onn_roku_tv_active_app")
    entry = entity_registry.async_get("sensor.58_onn_roku_tv_active_app")
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_active_app"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "Antenna TV"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == '58" Onn Roku TV Active App'
    assert state.attributes.get(ATTR_ICON) == "mdi:application"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.58_onn_roku_tv_active_app_id")
    entry = entity_registry.async_get("sensor.58_onn_roku_tv_active_app_id")
    assert entry
    assert state
    assert entry.unique_id == "YN00H5555555_active_app_id"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "tvinput.dtv"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == '58" Onn Roku TV Active App ID'
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
