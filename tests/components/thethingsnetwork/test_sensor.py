"""Define tests for the The Things Network sensor."""

import logging
from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import (
    APP_ID,
    DATA_UPDATE,
    DATA_WITH_ATTRS,
    DATA_WITH_ENTITY_CATEGORY,
    DATA_WITH_INVALID_ATTRS,
    DEVICE_FIELD,
    DEVICE_FIELD_2,
    DEVICE_ID,
    DEVICE_ID_2,
    DOMAIN,
)


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test a working configurations."""

    await init_integration(hass, mock_config_entry)

    # Check devices
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{APP_ID}_{DEVICE_ID}")}
        ).name
        == DEVICE_ID
    )

    # Check entities
    assert entity_registry.async_get(f"sensor.{DEVICE_ID}_{DEVICE_FIELD}")

    assert not entity_registry.async_get(f"sensor.{DEVICE_ID_2}_{DEVICE_FIELD}")
    push_callback = mock_ttnclient.call_args.kwargs["push_callback"]
    await push_callback(DATA_UPDATE)
    assert entity_registry.async_get(f"sensor.{DEVICE_ID_2}_{DEVICE_FIELD_2}")


async def test_sensor_with_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test sensors with decoder attributes (unit, device_class, state_class)."""
    mock_ttnclient.return_value.fetch_data = AsyncMock(return_value=DATA_WITH_ATTRS)

    await init_integration(hass, mock_config_entry)

    # Check BatV sensor has voltage attributes
    batv_entry = entity_registry.async_get(f"sensor.{DEVICE_ID}_batv")
    assert batv_entry is not None

    batv_state = hass.states.get(batv_entry.entity_id)
    assert batv_state is not None
    assert batv_state.attributes.get("device_class") == SensorDeviceClass.VOLTAGE
    assert batv_state.attributes.get("state_class") == SensorStateClass.MEASUREMENT
    assert batv_state.attributes.get("unit_of_measurement") == "V"
    assert float(batv_state.state) == 3.6

    # Check temperature sensor has temperature attributes
    # friendly_name "Room Temperature" changes entity_id slug
    temp_entry = entity_registry.async_get(f"sensor.{DEVICE_ID}_room_temperature")
    assert temp_entry is not None

    temp_state = hass.states.get(temp_entry.entity_id)
    assert temp_state is not None
    assert temp_state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE
    assert temp_state.attributes.get("state_class") == SensorStateClass.MEASUREMENT
    assert temp_state.attributes.get("unit_of_measurement") == "°C"


async def test_sensor_friendly_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test that friendly_name from decoder overrides entity name."""
    mock_ttnclient.return_value.fetch_data = AsyncMock(return_value=DATA_WITH_ATTRS)

    await init_integration(hass, mock_config_entry)

    # friendly_name "Room Temperature" changes entity_id slug
    temp_entry = entity_registry.async_get(f"sensor.{DEVICE_ID}_room_temperature")
    assert temp_entry is not None

    temp_state = hass.states.get(temp_entry.entity_id)
    assert temp_state is not None
    assert temp_state.attributes.get("friendly_name") == f"{DEVICE_ID} Room Temperature"


async def test_sensor_display_precision(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test suggested_display_precision is set from decoder attributes."""
    mock_ttnclient.return_value.fetch_data = AsyncMock(return_value=DATA_WITH_ATTRS)

    await init_integration(hass, mock_config_entry)

    # friendly_name "Room Temperature" changes entity_id slug
    temp_entry = entity_registry.async_get(f"sensor.{DEVICE_ID}_room_temperature")
    assert temp_entry is not None
    assert temp_entry.options.get("sensor", {}).get("suggested_display_precision") == 1


async def test_sensor_entity_category(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test entity_category is set from decoder attributes."""
    mock_ttnclient.return_value.fetch_data = AsyncMock(
        return_value=DATA_WITH_ENTITY_CATEGORY
    )

    await init_integration(hass, mock_config_entry)

    rssi_entry = entity_registry.async_get(f"sensor.{DEVICE_ID}_rssi")
    assert rssi_entry is not None
    assert rssi_entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_sensor_invalid_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
    caplog: logging.LoggerAdapter,
) -> None:
    """Test that invalid decoder attributes log warnings but still create entities."""
    mock_ttnclient.return_value.fetch_data = AsyncMock(
        return_value=DATA_WITH_INVALID_ATTRS
    )

    with caplog.at_level(logging.WARNING):
        await init_integration(hass, mock_config_entry)

    # Entity should still be created
    sensor_entry = entity_registry.async_get(f"sensor.{DEVICE_ID}_sensor_x")
    assert sensor_entry is not None

    # Warning should have been logged
    assert "unsupported device_class" in caplog.text


async def test_sensor_attr_fields_filtered(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test that TTNSensorAttribute fields are not created as entities."""
    mock_ttnclient.return_value.fetch_data = AsyncMock(return_value=DATA_WITH_ATTRS)

    await init_integration(hass, mock_config_entry)

    # Attribute fields should NOT create entities
    assert not entity_registry.async_get(
        f"sensor.{DEVICE_ID}__sensor_attr_batv_unit"
    )
    assert not entity_registry.async_get(
        f"sensor.{DEVICE_ID}__sensor_attr_batv_device_class"
    )

    # Only actual sensor fields should exist
    assert entity_registry.async_get(f"sensor.{DEVICE_ID}_batv")
    # friendly_name "Room Temperature" changes entity_id slug
    assert entity_registry.async_get(f"sensor.{DEVICE_ID}_room_temperature")
