"""Tests for the Hinen sensor platform."""

import pytest

from homeassistant.components.hinen_power.const import ATTR_STATUS, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import ComponentSetup


async def test_sensors_added_correctly(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sensors are added correctly."""
    await setup_integration()
    await hass.async_block_till_done()

    # Test status sensor
    status_entity = entity_registry.async_get("sensor.test_hinen_device_status")
    assert status_entity is not None
    assert status_entity.unique_id == "12345678_device_12345_status"

    device_entries = device_registry.async_get_devices(
        identifiers={(DOMAIN, "12345678_device_12345")}
    )
    assert len(device_entries) == 1
    assert device_entries[0].manufacturer == "Hinen"
    assert device_entries[0].serial_number == "SN123456789"


async def test_sensor_states(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test sensor states are correctly reported."""
    await setup_integration()
    await hass.async_block_till_done()

    # Test status sensor state
    status_state = hass.states.get("sensor.test_hinen_device_status")
    assert status_state is not None
    assert status_state.state == "normal"


@pytest.mark.parametrize("status_value", [-1, None], ids=["unknown_enum", "none"])
async def test_sensor_native_value_unknown_state(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    status_value: int | None,
) -> None:
    """Test the status sensor reports unknown when the device status is unknown."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await setup_integration()
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    coordinator.data["device_12345"][ATTR_STATUS] = status_value
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    status_state = hass.states.get("sensor.test_hinen_device_status")
    assert status_state is not None
    assert status_state.state == "unknown"


async def test_sensor_unavailable_when_device_missing(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test the sensor becomes unavailable when the coordinator device data is missing."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await setup_integration()
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    coordinator.data.pop("device_12345", None)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    status_state = hass.states.get("sensor.test_hinen_device_status")
    assert status_state is not None
    assert status_state.state == STATE_UNAVAILABLE
