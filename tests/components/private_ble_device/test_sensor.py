"""Tests for sensors."""


from habluetooth.advertisement_tracker import ADVERTISING_TIMES_NEEDED

from homeassistant.components.bluetooth import async_set_fallback_availability_interval
from homeassistant.core import HomeAssistant

from . import (
    MAC_RPA_VALID_1,
    MAC_RPA_VALID_2,
    async_inject_broadcast,
    async_mock_config_entry,
)


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


async def test_estimated_broadcast_interval(
    hass: HomeAssistant,
    enable_bluetooth: None,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test sensors get value when we receive a broadcast."""
    await async_mock_config_entry(hass)
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)

    # With no fallback and no learned interval, we should use the global default

    state = hass.states.get(
        "sensor.private_ble_device_000000_estimated_broadcast_interval"
    )
    assert state
    assert state.state == "900"

    # Fallback interval trumps const default

    async_set_fallback_availability_interval(hass, MAC_RPA_VALID_1, 90)
    await async_inject_broadcast(hass, MAC_RPA_VALID_1.upper())

    state = hass.states.get(
        "sensor.private_ble_device_000000_estimated_broadcast_interval"
    )
    assert state
    assert state.state == "90.0"

    # Learned broadcast interval takes over from fallback interval

    for i in range(ADVERTISING_TIMES_NEEDED):
        await async_inject_broadcast(
            hass, MAC_RPA_VALID_1, mfr_data=bytes(i), broadcast_time=i * 10
        )

    state = hass.states.get(
        "sensor.private_ble_device_000000_estimated_broadcast_interval"
    )
    assert state
    assert state.state == "10.0"

    # MAC address changes, the broadcast interval is kept

    await async_inject_broadcast(hass, MAC_RPA_VALID_2.upper())

    state = hass.states.get(
        "sensor.private_ble_device_000000_estimated_broadcast_interval"
    )
    assert state
    assert state.state == "10.0"
