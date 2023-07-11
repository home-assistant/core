"""Tests for the sensors provided by the Tailscale integration."""
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.tailscale.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_tailscale_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Tailscale sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.router_expires")
    entry = entity_registry.async_get("sensor.router_expires")
    assert entry
    assert state
    assert entry.unique_id == "123457_expires"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "2022-02-25T09:49:06+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "router Expires"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.router_last_seen")
    entry = entity_registry.async_get("sensor.router_last_seen")
    assert entry
    assert state
    assert entry.unique_id == "123457_last_seen"
    assert entry.entity_category is None
    assert state.state == "2021-11-15T20:37:03+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "router Last seen"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.router_ip_address")
    entry = entity_registry.async_get("sensor.router_ip_address")
    assert entry
    assert state
    assert entry.unique_id == "123457_ip"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == "100.11.11.112"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "router IP address"
    assert state.attributes.get(ATTR_ICON) == "mdi:ip-network"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "123457")}
    assert device_entry.manufacturer == "Tailscale Inc."
    assert device_entry.model == "linux"
    assert device_entry.name == "router"
    assert device_entry.entry_type == dr.DeviceEntryType.SERVICE
    assert device_entry.sw_version == "1.14.0-t5cff36945-g809e87bba"
    assert (
        device_entry.configuration_url
        == "https://login.tailscale.com/admin/machines/100.11.11.112"
    )
