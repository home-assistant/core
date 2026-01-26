"""Define tests for the The Things Network sensor."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import (
    APP_ID,
    DATA_UPDATE,
    DATA_WIFI_SCAN,
    DEVICE_FIELD,
    DEVICE_FIELD_2,
    DEVICE_ID,
    DEVICE_ID_2,
    DOMAIN,
    TRACKER_DEVICE_ID,
    WIFI_SCAN_DATA,
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


async def test_sensor_array_value(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test sensor with array value (Wi-Fi scan data)."""
    # Setup with Wi-Fi scan data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_WIFI_SCAN

    await init_integration(hass, mock_config_entry)

    # Verify sensor entity is created for Wi-Fi scan
    entity_id = f"sensor.{TRACKER_DEVICE_ID}_wi_fi_scan_5001"
    entity = entity_registry.async_get(entity_id)
    assert entity

    # Check state - should be the count of array items
    state = hass.states.get(entity_id)
    assert state
    assert state.state == str(len(WIFI_SCAN_DATA))

    # Check attributes - should have items_count and individual AP data
    assert state.attributes["items_count"] == len(WIFI_SCAN_DATA)

    # Verify individual access point attributes
    for idx, ap in enumerate(WIFI_SCAN_DATA, 1):
        assert state.attributes[f"ap_{idx}_mac"] == ap["mac"]
        assert state.attributes[f"ap_{idx}_rssi"] == ap["rssi"]
