"""Tests for the sensors provided by the Tailscale integration."""
from homeassistant.components.binary_sensor import (
    STATE_OFF,
    STATE_ON,
    BinarySensorDeviceClass,
)
from homeassistant.components.tailscale.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry


async def test_tailscale_binary_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Tailscale binary sensors."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("binary_sensor.frencks_iphone_client")
    entry = entity_registry.async_get("binary_sensor.frencks_iphone_client")
    assert entry
    assert state
    assert entry.unique_id == "123456_update_available"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "frencks-iphone Client"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.UPDATE
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("binary_sensor.frencks_iphone_supports_hairpinning")
    entry = entity_registry.async_get(
        "binary_sensor.frencks_iphone_supports_hairpinning"
    )
    assert entry
    assert state
    assert entry.unique_id == "123456_client_supports_hair_pinning"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "frencks-iphone Supports hairpinning"
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.frencks_iphone_supports_ipv6")
    entry = entity_registry.async_get("binary_sensor.frencks_iphone_supports_ipv6")
    assert entry
    assert state
    assert entry.unique_id == "123456_client_supports_ipv6"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "frencks-iphone Supports IPv6"
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.frencks_iphone_supports_pcp")
    entry = entity_registry.async_get("binary_sensor.frencks_iphone_supports_pcp")
    assert entry
    assert state
    assert entry.unique_id == "123456_client_supports_pcp"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "frencks-iphone Supports PCP"
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.frencks_iphone_supports_nat_pmp")
    entry = entity_registry.async_get("binary_sensor.frencks_iphone_supports_nat_pmp")
    assert entry
    assert state
    assert entry.unique_id == "123456_client_supports_pmp"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "frencks-iphone Supports NAT-PMP"
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.frencks_iphone_supports_udp")
    entry = entity_registry.async_get("binary_sensor.frencks_iphone_supports_udp")
    assert entry
    assert state
    assert entry.unique_id == "123456_client_supports_udp"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "frencks-iphone Supports UDP"
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("binary_sensor.frencks_iphone_supports_upnp")
    entry = entity_registry.async_get("binary_sensor.frencks_iphone_supports_upnp")
    assert entry
    assert state
    assert entry.unique_id == "123456_client_supports_upnp"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "frencks-iphone Supports UPnP"
    assert state.attributes.get(ATTR_ICON) == "mdi:wan"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "123456")}
    assert device_entry.manufacturer == "Tailscale Inc."
    assert device_entry.model == "iOS"
    assert device_entry.name == "frencks-iphone"
    assert device_entry.entry_type == dr.DeviceEntryType.SERVICE
    assert device_entry.sw_version == "1.12.3-td91ea7286-ge1bbbd90c"
    assert (
        device_entry.configuration_url
        == "https://login.tailscale.com/admin/machines/100.11.11.111"
    )
