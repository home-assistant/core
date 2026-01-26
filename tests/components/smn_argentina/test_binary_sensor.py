"""Test the SMN binary sensor entities."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_alert_sensor_on(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_alerts_data_with_active,
) -> None:
    """Test alert sensor is ON when alerts are active."""
    # Update mock to return active alerts
    mock_smn_api_client.async_get_alerts.return_value = mock_alerts_data_with_active

    await init_integration(hass)

    # Get main alert sensor
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_weather_alert")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["active_alert_count"] == 2
    assert "tormenta" in state.attributes["alert_summary"]
    assert "lluvia" in state.attributes["alert_summary"]


async def test_alert_sensor_off(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test alert sensor is OFF when no alerts are active."""
    await init_integration(hass)

    # Get main alert sensor
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_weather_alert")
    assert state is not None
    assert state.state == STATE_OFF


async def test_event_alert_sensors(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_alerts_data_with_active,
) -> None:
    """Test individual event alert sensors."""
    # Update mock to return active alerts
    mock_smn_api_client.async_get_alerts.return_value = mock_alerts_data_with_active

    await init_integration(hass)

    # Test tormenta sensor is ON (event ID 41, level 3 in mock data)
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_thunderstorm_alert")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["level"] == 3
    assert state.attributes["severity"] == "warning"

    # Test lluvia sensor is ON (event ID 37, level 2 in mock data)
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_rain_alert")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["level"] == 2

    # Test nevada sensor is OFF (not in mock data)
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_snow_alert")
    assert state is not None
    assert state.state == STATE_OFF


async def test_all_alert_sensor_types(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test all alert sensor types are created."""
    await init_integration(hass)

    # List of all expected alert sensors
    expected_sensors = [
        "weather_alert",  # Main alert sensor
        "rain_alert",  # lluvia
        "wind_alert",  # viento
        "fog_alert",  # niebla
        "thunderstorm_alert",  # tormenta
        "snow_alert",  # nevada
        "high_temperature_alert",  # temperatura_alta
        "low_temperature_alert",  # temperatura_baja
        "volcanic_ash_alert",  # ceniza
        "dust_alert",  # polvo
        "zonda_wind_alert",  # zonda
        "smoke_alert",  # humo
        "short_term_alert",  # Short-term alerts
    ]

    for sensor_name in expected_sensors:
        entity_id = f"binary_sensor.ciudad_de_buenos_aires_{sensor_name}"
        state = hass.states.get(entity_id)
        assert state is not None, f"Sensor {entity_id} not found"
        assert state.state in [STATE_ON, STATE_OFF]


async def test_shortterm_alert_sensor(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_shortterm_alerts,
) -> None:
    """Test short-term alert sensor."""
    # Update mock to return short-term alerts
    mock_smn_api_client.async_get_shortterm_alerts.return_value = mock_shortterm_alerts

    await init_integration(hass)

    # Get short-term alert sensor
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_short_term_alert")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["alert_count"] == 1
    assert "TORMENTAS FUERTES" in state.attributes["alerts"][0]["title"]
    assert "BUENOS AIRES: Ayacucho" in str(state.attributes["alerts"][0]["zones"])


async def test_alert_sensor_icons(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_alerts_data_with_active,
) -> None:
    """Test alert sensors have correct MDI icons."""
    # Update mock to return active alerts
    mock_smn_api_client.async_get_alerts.return_value = mock_alerts_data_with_active

    await init_integration(hass)

    # Test main alert sensor icon
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_weather_alert")
    assert state is not None
    assert state.attributes["icon"] == "mdi:alert"

    # Test tormenta sensor icon
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_thunderstorm_alert")
    assert state is not None
    assert state.attributes["icon"] == "mdi:weather-lightning"

    # Test lluvia sensor icon
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_rain_alert")
    assert state is not None
    assert state.attributes["icon"] == "mdi:weather-rainy"


async def test_alert_sensor_attributes(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_alerts_data_with_active,
) -> None:
    """Test alert sensor attributes are correct."""
    # Update mock to return active alerts
    mock_smn_api_client.async_get_alerts.return_value = mock_alerts_data_with_active

    await init_integration(hass)

    # Test main alert sensor attributes
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_weather_alert")
    assert state is not None
    assert "active_alert_count" in state.attributes
    assert "max_severity" in state.attributes
    assert "max_level" in state.attributes
    assert "alert_summary" in state.attributes
    assert "active_alerts" in state.attributes
    assert state.attributes["device_class"] == "safety"


async def test_individual_alert_sensor_attributes(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_alerts_data_with_active,
) -> None:
    """Test individual alert sensor attributes."""
    # Update mock to return active alerts
    mock_smn_api_client.async_get_alerts.return_value = mock_alerts_data_with_active

    await init_integration(hass)

    # Test thunderstorm sensor attributes
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_thunderstorm_alert")
    assert state is not None
    assert "level" in state.attributes
    assert "severity" in state.attributes
    assert state.attributes["level"] == 3
    assert state.attributes["severity"] == "warning"
    assert state.attributes["device_class"] == "safety"


async def test_alert_sensor_update(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
    mock_alerts_data_with_active,
) -> None:
    """Test alert sensor updates when data changes."""
    # Start with no alerts
    entry = await init_integration(hass)

    # Get main alert sensor - should be OFF
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_weather_alert")
    assert state is not None
    assert state.state == STATE_OFF

    # Update mock to return active alerts
    mock_smn_api_client.async_get_alerts.return_value = mock_alerts_data_with_active

    # Force update
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Get main alert sensor - should now be ON
    state = hass.states.get("binary_sensor.ciudad_de_buenos_aires_weather_alert")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["active_alert_count"] > 0
