"""Tests for the sensors provided by the Tailscale integration."""
from homeassistant.components.binary_sensor import STATE_ON, BinarySensorDeviceClass
from homeassistant.components.tailscale.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Frencks-iPhone Client"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.UPDATE
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, "123456")}
    assert device_entry.manufacturer == "Tailscale Inc."
    assert device_entry.model == "iOS"
    assert device_entry.name == "Frencks-iPhone"
    assert device_entry.entry_type == dr.DeviceEntryType.SERVICE
    assert device_entry.sw_version == "1.12.3-td91ea7286-ge1bbbd90c"
    assert (
        device_entry.configuration_url
        == "https://login.tailscale.com/admin/machines/100.11.11.111"
    )
