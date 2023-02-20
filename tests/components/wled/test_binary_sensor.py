"""Tests for the WLED binary sensor platform."""
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_available(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the firmware update binary sensor."""
    assert (state := hass.states.get("binary_sensor.wled_rgb_light_firmware"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.UPDATE
    assert state.state == STATE_ON
    assert ATTR_ICON not in state.attributes

    assert (entry := entity_registry.async_get("binary_sensor.wled_rgb_light_firmware"))
    assert entry.unique_id == "aabbccddeeff_update"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_no_update_available(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the update binary sensor. There is no update available."""
    assert (state := hass.states.get("binary_sensor.wled_websocket_firmware"))
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.UPDATE
    assert state.state == STATE_OFF
    assert ATTR_ICON not in state.attributes

    assert (entry := entity_registry.async_get("binary_sensor.wled_websocket_firmware"))
    assert entry.unique_id == "aabbccddeeff_update"
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the binary update sensor is disabled by default."""
    assert hass.states.get("binary_sensor.wled_rgb_light_firmware") is None

    assert (entry := entity_registry.async_get("binary_sensor.wled_rgb_light_firmware"))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
