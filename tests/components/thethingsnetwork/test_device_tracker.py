"""Define tests for The Things Network device tracker."""

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration
from .conftest import (
    APP_ID,
    DATA_BATTERY_ONLY,
    DATA_GPS,
    DATA_GPS_AND_WIFI,
    DATA_WIFI_NEWER,
    DATA_WIFI_OLDER,
    DATA_WIFI_SCAN,
    DEVICE_ID,
    DOMAIN,
    GPS_LATITUDE,
    GPS_LONGITUDE,
    TRACKER_DEVICE_ID,
    WIFI_SCAN_DATA,
    WIFI_SCAN_DATA_NEW,
)


async def test_device_tracker_wifi_scan(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test device tracker creation with Wi-Fi scan data."""
    # Setup with Wi-Fi scan data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_WIFI_SCAN

    await init_integration(hass, mock_config_entry)

    # Verify device tracker entity is created
    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == TRACKER_DEVICE_ID
    assert entity.entity_category is None  # Not diagnostic

    # Verify device is created
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{APP_ID}_{TRACKER_DEVICE_ID}")}
    )
    assert device
    assert device.name == TRACKER_DEVICE_ID

    # Check state and attributes
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"  # No GPS coordinates, so unknown
    assert state.attributes["wifi_access_points_count"] == len(WIFI_SCAN_DATA)

    # Verify Wi-Fi access points are formatted correctly
    for idx, ap in enumerate(WIFI_SCAN_DATA, 1):
        assert state.attributes[f"wifi_ap_{idx}_mac"] == ap["mac"]
        assert state.attributes[f"wifi_ap_{idx}_rssi"] == ap["rssi"]

    # Verify Google Geolocation API format
    wifi_aps = state.attributes["wifi_access_points"]
    assert len(wifi_aps) == len(WIFI_SCAN_DATA)
    for idx, ap in enumerate(wifi_aps):
        assert ap["macAddress"] == WIFI_SCAN_DATA[idx]["mac"]
        assert ap["signalStrength"] == WIFI_SCAN_DATA[idx]["rssi"]


async def test_device_tracker_gps(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test device tracker with GPS coordinates."""
    # Setup with GPS data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_GPS

    await init_integration(hass, mock_config_entry)

    # Verify entity is created
    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.entity_category is None  # Not diagnostic

    # Check GPS coordinates
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == GPS_LATITUDE
    assert state.attributes[ATTR_LONGITUDE] == GPS_LONGITUDE

    # No Wi-Fi attributes when only GPS present
    assert "wifi_access_points" not in state.attributes


async def test_device_tracker_gps_and_wifi(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test device tracker with both GPS and Wi-Fi data."""
    # Setup with combined data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_GPS_AND_WIFI

    await init_integration(hass, mock_config_entry)

    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    state = hass.states.get(entity_id)
    assert state

    # Both GPS coordinates and Wi-Fi attributes should be present
    assert state.attributes[ATTR_LATITUDE] == GPS_LATITUDE
    assert state.attributes[ATTR_LONGITUDE] == GPS_LONGITUDE
    assert state.attributes["wifi_access_points_count"] == len(WIFI_SCAN_DATA)
    assert "wifi_access_points" in state.attributes


async def test_device_tracker_no_location_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test that device tracker is not created without location data."""
    # Setup with battery data only (no location)
    mock_ttnclient.return_value.fetch_data.return_value = DATA_BATTERY_ONLY

    await init_integration(hass, mock_config_entry)

    # Verify no device tracker is created
    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity is None


async def test_device_tracker_update_with_location_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test device tracker only updates when location data is present."""
    # Start with GPS data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_GPS

    await init_integration(hass, mock_config_entry)

    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    state = hass.states.get(entity_id)
    assert state
    initial_state_changed = state.last_changed

    # Push battery-only update (no location data)
    push_callback = mock_ttnclient.call_args.kwargs["push_callback"]
    await push_callback(DATA_BATTERY_ONLY)
    await hass.async_block_till_done()

    # State should not have changed (no update without location data)
    state = hass.states.get(entity_id)
    assert state.last_changed == initial_state_changed

    # Push Wi-Fi scan data
    await push_callback(DATA_WIFI_SCAN)
    await hass.async_block_till_done()

    # State should have updated now
    state = hass.states.get(entity_id)
    assert state.last_changed != initial_state_changed
    assert "wifi_access_points" in state.attributes


async def test_device_tracker_dynamic_addition(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test dynamic addition of device tracker when location data appears."""
    # Start without location data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_BATTERY_ONLY

    await init_integration(hass, mock_config_entry)

    # Verify no tracker initially
    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity is None

    # Push GPS data - should create tracker
    push_callback = mock_ttnclient.call_args.kwargs["push_callback"]
    await push_callback(DATA_GPS)
    await hass.async_block_till_done()

    # Verify tracker is now created
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == TRACKER_DEVICE_ID

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == GPS_LATITUDE
    assert state.attributes[ATTR_LONGITUDE] == GPS_LONGITUDE


async def test_regular_sensor_with_location_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test that regular sensors are still created alongside device tracker."""
    # Setup with GPS data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_GPS

    await init_integration(hass, mock_config_entry)

    # Verify device tracker exists
    tracker_entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    assert entity_registry.async_get(tracker_entity_id)

    # Verify sensor entities also exist
    lat_sensor_id = f"sensor.{TRACKER_DEVICE_ID}_latitude_4198"
    lon_sensor_id = f"sensor.{TRACKER_DEVICE_ID}_longitude_4197"
    assert entity_registry.async_get(lat_sensor_id)
    assert entity_registry.async_get(lon_sensor_id)

    # Check sensor values
    lat_state = hass.states.get(lat_sensor_id)
    lon_state = hass.states.get(lon_sensor_id)
    assert float(lat_state.state) == GPS_LATITUDE
    assert float(lon_state.state) == GPS_LONGITUDE


async def test_sensor_with_no_location_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test that regular sensors work for devices without location data."""
    # Start with existing sensor data
    existing_data = {
        DEVICE_ID: mock_ttnclient.return_value.fetch_data.return_value[DEVICE_ID]
    }
    mock_ttnclient.return_value.fetch_data.return_value = existing_data

    await init_integration(hass, mock_config_entry)

    # Verify no tracker for non-location device
    tracker_entity_id = f"{DEVICE_TRACKER_DOMAIN}.{DEVICE_ID}"
    assert entity_registry.async_get(tracker_entity_id) is None

    # But sensor should still exist
    sensor_entity_id = f"sensor.{DEVICE_ID}_a_field"
    assert entity_registry.async_get(sensor_entity_id)


async def test_geocoded_location_fallback(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test geocoded location is used when no GPS available."""
    # Setup with Wi-Fi scan data only (no GPS)
    mock_ttnclient.return_value.fetch_data.return_value = DATA_WIFI_SCAN

    await init_integration(hass, mock_config_entry)

    # Get the entity
    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity

    # Initial state should be unknown (no location)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes

    # Get the entity component
    component = hass.data.get("entity_components", {}).get("device_tracker")
    assert component
    entity_obj = component.get_entity(entity_id)
    assert entity_obj

    # Set geocoded location
    geocoded_lat = 51.0340168
    geocoded_lon = 3.7415962
    geocoded_accuracy = 26.147

    entity_obj.set_geocoded_location(geocoded_lat, geocoded_lon, geocoded_accuracy)
    await hass.async_block_till_done()

    # Now the geocoded location should be used
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == geocoded_lat
    assert state.attributes[ATTR_LONGITUDE] == geocoded_lon
    assert state.attributes["geocoded_latitude"] == geocoded_lat
    assert state.attributes["geocoded_longitude"] == geocoded_lon
    assert state.attributes["geocoded_accuracy"] == geocoded_accuracy
    assert state.attributes["location_source"] == "geocoded"


async def test_gps_priority_over_geocoded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test GPS coordinates take priority over geocoded location."""
    # Setup with GPS data
    mock_ttnclient.return_value.fetch_data.return_value = DATA_GPS

    await init_integration(hass, mock_config_entry)

    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity

    # Get the entity component
    component = hass.data.get("entity_components", {}).get("device_tracker")
    assert component
    entity_obj = component.get_entity(entity_id)
    assert entity_obj

    # Set geocoded location (different from GPS)
    geocoded_lat = 51.0340168
    geocoded_lon = 3.7415962
    geocoded_accuracy = 26.147

    entity_obj.set_geocoded_location(geocoded_lat, geocoded_lon, geocoded_accuracy)
    await hass.async_block_till_done()

    # GPS should take priority
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == GPS_LATITUDE  # GPS, not geocoded
    assert state.attributes[ATTR_LONGITUDE] == GPS_LONGITUDE  # GPS, not geocoded

    # But geocoded attributes should still be present
    assert state.attributes["geocoded_latitude"] == geocoded_lat
    assert state.attributes["geocoded_longitude"] == geocoded_lon
    assert state.attributes["geocoded_accuracy"] == geocoded_accuracy
    assert state.attributes["location_source"] == "gps"


async def test_geocoded_location_without_accuracy(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test geocoded location can be set without accuracy parameter."""
    # Setup with Wi-Fi scan data only
    mock_ttnclient.return_value.fetch_data.return_value = DATA_WIFI_SCAN

    await init_integration(hass, mock_config_entry)

    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"

    # Get the entity component
    component = hass.data.get("entity_components", {}).get("device_tracker")
    assert component
    entity_obj = component.get_entity(entity_id)
    assert entity_obj

    # Set geocoded location without accuracy
    geocoded_lat = 51.0340168
    geocoded_lon = 3.7415962

    entity_obj.set_geocoded_location(geocoded_lat, geocoded_lon)
    await hass.async_block_till_done()

    # Verify location is set without accuracy
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_LATITUDE] == geocoded_lat
    assert state.attributes[ATTR_LONGITUDE] == geocoded_lon
    assert state.attributes["geocoded_latitude"] == geocoded_lat
    assert state.attributes["geocoded_longitude"] == geocoded_lon
    assert "geocoded_accuracy" not in state.attributes  # Should not be present
    assert state.attributes["location_source"] == "geocoded"


async def test_out_of_order_messages_ignored(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ttnclient,
    mock_config_entry,
) -> None:
    """Test that older messages received after newer ones are ignored."""
    # Setup with newer timestamp data first
    mock_ttnclient.return_value.fetch_data.return_value = DATA_WIFI_NEWER

    await init_integration(hass, mock_config_entry)

    entity_id = f"{DEVICE_TRACKER_DOMAIN}.{TRACKER_DEVICE_ID}"
    entity = entity_registry.async_get(entity_id)
    assert entity

    # Verify we have the newer data
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["wifi_access_points_count"] == len(WIFI_SCAN_DATA_NEW)
    assert state.attributes["wifi_timestamp"] == 1710331200000

    # Get the coordinator to simulate receiving old data
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Now push older data (simulating device sending buffered old measurement)
    await coordinator._push_callback(DATA_WIFI_OLDER)
    await hass.async_block_till_done()

    # Verify old data was ignored - we should still have the new data
    state = hass.states.get(entity_id)
    assert state
    # Should still be the newer data with 2 APs, not the old data with 1 AP
    assert state.attributes["wifi_access_points_count"] == len(WIFI_SCAN_DATA_NEW)
    assert state.attributes["wifi_timestamp"] == 1710331200000  # Still newer timestamp
