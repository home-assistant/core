"""Tests for the Rituals Perfume Genie sensor platform."""
from homeassistant.components.rituals_perfume_genie.sensor import (
    BATTERY_SUFFIX,
    FILL_SUFFIX,
    PERFUME_SUFFIX,
    WIFI_SUFFIX,
    SensorDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from .common import (
    init_integration,
    mock_config_entry,
    mock_diffuser_v1_battery_cartridge,
    mock_diffuser_v2_no_battery_no_cartridge,
)


async def test_sensors_diffuser_v1_battery_cartridge(hass: HomeAssistant) -> None:
    """Test the creation and values of the Rituals Perfume Genie sensors."""
    config_entry = mock_config_entry(unique_id="id_123_sensor_test_diffuser_v1")
    diffuser = mock_diffuser_v1_battery_cartridge()
    await init_integration(hass, config_entry, [diffuser])
    registry = entity_registry.async_get(hass)
    hublot = diffuser.hublot

    state = hass.states.get("sensor.genie_perfume")
    assert state
    assert state.state == diffuser.perfume
    assert state.attributes.get(ATTR_ICON) == "mdi:tag-text"

    entry = registry.async_get("sensor.genie_perfume")
    assert entry
    assert entry.unique_id == f"{hublot}{PERFUME_SUFFIX}"

    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == diffuser.fill
    assert state.attributes.get(ATTR_ICON) == "mdi:beaker"

    entry = registry.async_get("sensor.genie_fill")
    assert entry
    assert entry.unique_id == f"{hublot}{FILL_SUFFIX}"

    state = hass.states.get("sensor.genie_battery")
    assert state
    assert state.state == str(diffuser.battery_percentage)
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.genie_battery")
    assert entry
    assert entry.unique_id == f"{hublot}{BATTERY_SUFFIX}"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.genie_wifi")
    assert state
    assert state.state == str(diffuser.wifi_percentage)
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = registry.async_get("sensor.genie_wifi")
    assert entry
    assert entry.unique_id == f"{hublot}{WIFI_SUFFIX}"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_sensors_diffuser_v2_no_battery_no_cartridge(hass: HomeAssistant) -> None:
    """Test the creation and values of the Rituals Perfume Genie sensors."""
    config_entry = mock_config_entry(unique_id="id_123_sensor_test_diffuser_v2")

    await init_integration(
        hass, config_entry, [mock_diffuser_v2_no_battery_no_cartridge()]
    )

    state = hass.states.get("sensor.genie_v2_perfume")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:tag-remove"

    state = hass.states.get("sensor.genie_v2_fill")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:beaker-question"
