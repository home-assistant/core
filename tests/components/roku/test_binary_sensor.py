"""Tests for the sensors provided by the Roku integration."""
from homeassistant.components.binary_sensor import STATE_OFF
from homeassistant.components.roku.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.components.roku import UPNP_SERIAL, setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_roku_binary_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Roku binary sensors."""
    await setup_integration(hass, aioclient_mock)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("binary_sensor.my_roku_3_supports_airplay")
    entry = entity_registry.async_get(
        "binary_sensor.my_roku_3_supports_airplay"
    )
    assert entry
    assert state
    assert entry.unique_id == f"{UPNP_SERIAL}_supports_airplay"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "My Roku 3 Supports Airplay"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, UPNP_SERIAL)}
    assert device_entry.manufacturer == "Roku"
    assert device_entry.model == "4200X"
    assert device_entry.name == "My Roku 3"
    assert device_entry.entry_type == dr.DeviceEntryType.DEVICE
    assert device_entry.sw_version == "7.5.0"
