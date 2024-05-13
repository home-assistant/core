"""Tests for sensors."""


from homeassistant.core import HomeAssistant

from . import MAC_RPA_VALID_1, async_inject_broadcast, async_mock_config_entry


async def test_sensor_unavailable(
    hass: HomeAssistant,
    enable_bluetooth: None,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test sensors are unavailable."""
    await async_mock_config_entry(hass)

    state = hass.states.get("sensor.private_ble_device_000000_signal_strength")
    assert state
    assert state.state == "unavailable"


async def test_sensors_already_home(
    hass: HomeAssistant,
    enable_bluetooth: None,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test sensors get value when we start at home."""
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    await async_mock_config_entry(hass)

    state = hass.states.get("sensor.private_ble_device_000000_signal_strength")
    assert state
    assert state.state == "-63"


async def test_sensors_come_home(
    hass: HomeAssistant,
    enable_bluetooth: None,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test sensors get value when we receive a broadcast."""
    await async_mock_config_entry(hass)
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)

    state = hass.states.get("sensor.private_ble_device_000000_signal_strength")
    assert state
    assert state.state == "-63"
