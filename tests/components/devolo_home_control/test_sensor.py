"""Tests for the devolo Home Control sensor platform."""
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .mocks import HomeControlMock, HomeControlMockConsumption, HomeControlMockSensor


async def test_temperature_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup of a temperature sensor device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSensor()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test_temperature")
    assert state == snapshot
    assert entity_registry.async_get(f"{DOMAIN}.test_temperature") == snapshot


async def test_battery_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a battery sensor device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSensor()
    test_gateway.devices["Test"].battery_level = 25
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test_battery_level")
    assert state == snapshot
    assert entity_registry.async_get(f"{DOMAIN}.test_battery_level") == snapshot

    # Emulate websocket message: value changed
    test_gateway.publisher.dispatch("Test", ("Test", 10, "battery_level"))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test_battery_level").state == "10"


async def test_consumption_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test setup and state change of a consumption sensor device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockConsumption()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test_current_consumption")
    assert state == snapshot
    assert entity_registry.async_get(f"{DOMAIN}.test_current_consumption") == snapshot

    state = hass.states.get(f"{DOMAIN}.test_total_consumption")
    assert state == snapshot
    assert entity_registry.async_get(f"{DOMAIN}.test_total_consumption") == snapshot

    # Emulate websocket message: value changed
    test_gateway.devices["Test"].consumption_property["devolo.Meter:Test"].total = 50.0
    test_gateway.publisher.dispatch("Test", ("devolo.Meter:Test", 50.0))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test_total_consumption").state == "50.0"

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert (
        hass.states.get(f"{DOMAIN}.test_current_consumption").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(f"{DOMAIN}.test_total_consumption").state == STATE_UNAVAILABLE
    )


async def test_voltage_sensor(hass: HomeAssistant) -> None:
    """Test disabled setup of a voltage sensor device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockConsumption()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test_voltage")
    assert state is None


async def test_sensor_change(hass: HomeAssistant) -> None:
    """Test state change of a sensor device."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSensor()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Emulate websocket message: value changed
    test_gateway.publisher.dispatch("Test", ("devolo.MultiLevelSensor:Test", 50.0))
    await hass.async_block_till_done()
    state = hass.states.get(f"{DOMAIN}.test_temperature")
    assert state.state == "50.0"

    # Emulate websocket message: device went offline
    test_gateway.devices["Test"].status = 1
    test_gateway.publisher.dispatch("Test", ("Status", False, "status"))
    await hass.async_block_till_done()
    assert hass.states.get(f"{DOMAIN}.test_temperature").state == STATE_UNAVAILABLE


async def test_remove_from_hass(hass: HomeAssistant) -> None:
    """Test removing entity."""
    entry = configure_integration(hass)
    test_gateway = HomeControlMockSensor()
    with patch(
        "homeassistant.components.devolo_home_control.HomeControl",
        side_effect=[test_gateway, HomeControlMock()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(f"{DOMAIN}.test_temperature")
    assert state is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert test_gateway.publisher.unregister.call_count == 1
