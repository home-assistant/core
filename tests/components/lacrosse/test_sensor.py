"""Tests for the LaCrosse sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.components.lacrosse.sensor import (
    SENSOR_TYPES,
    LaCrosseSensor,
    setup_platform,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant


async def test_setup_platform_imports_yaml_configuration(hass: HomeAssistant) -> None:
    """Test YAML configuration is imported through a config flow."""
    config = {"sensors": {}, "device": "/dev/ttyUSB0"}

    with patch.object(
        hass.config_entries.flow, "async_init", new_callable=AsyncMock
    ) as mock_async_init:
        setup_platform(hass, config, MagicMock())
        await hass.async_block_till_done()

    mock_async_init.assert_awaited_once_with(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )


def test_device_uses_friendly_name(hass: HomeAssistant) -> None:
    """Test the device name falls back when no friendly name is configured."""
    receiver = MagicMock()
    named = LaCrosseSensor(
        hass,
        receiver,
        "/dev/ttyUSB0",
        "outdoor_temperature",
        None,
        {"id": 1, "friendly_name": "Outdoor"},
        SENSOR_TYPES["temperature"],
    )
    unnamed = LaCrosseSensor(
        hass,
        receiver,
        "/dev/ttyUSB0",
        "bedroom_temperature",
        None,
        {"id": 2},
        SENSOR_TYPES["temperature"],
    )

    assert named.device_info["name"] == "Outdoor"
    assert unnamed.device_info["name"] == "LaCrosse sensor 2"


def test_temperature_and_humidity_sensor_values(hass: HomeAssistant) -> None:
    """Test temperature and humidity sensor values update from the receiver."""
    receiver = MagicMock()
    sensor_data = MagicMock(
        temperature=21.5, humidity=54, low_battery=False, new_battery=True
    )
    config = {"id": 1}
    temperature = LaCrosseSensor(
        hass,
        receiver,
        "/dev/ttyUSB0",
        "outdoor_temperature",
        None,
        config,
        SENSOR_TYPES["temperature"],
    )
    humidity = LaCrosseSensor(
        hass,
        receiver,
        "/dev/ttyUSB0",
        "outdoor_humidity",
        None,
        config,
        SENSOR_TYPES["humidity"],
    )

    with patch.object(hass, "add_job") as mock_add_job:
        temperature._callback_lacrosse(sensor_data, None)
        humidity._callback_lacrosse(sensor_data, None)

    assert temperature.native_value == 21.5
    assert humidity.native_value == 54
    assert temperature.extra_state_attributes == {
        "low_battery": False,
        "new_battery": True,
    }
    assert mock_add_job.call_count == 2
    mock_add_job.assert_any_call(temperature.async_write_ha_state)
    mock_add_job.assert_any_call(humidity.async_write_ha_state)


async def test_sensor_registers_callback_when_added_to_hass(
    hass: HomeAssistant,
) -> None:
    """Test receiver callbacks are registered when the entity is added."""
    receiver = MagicMock()
    sensor = LaCrosseSensor(
        hass,
        receiver,
        "/dev/ttyUSB0",
        "outdoor_temperature",
        None,
        {"id": 1},
        SENSOR_TYPES["temperature"],
    )

    assert sensor.should_poll is False
    receiver.register_callback.assert_not_called()

    await sensor.async_added_to_hass()

    receiver.register_callback.assert_called_once_with(
        1, sensor._callback_lacrosse, None
    )


def test_battery_sensor_updates_and_expires(hass: HomeAssistant) -> None:
    """Test battery values, icons, and expiration scheduling."""
    receiver = MagicMock()
    sensor = LaCrosseSensor(
        hass,
        receiver,
        "/dev/ttyUSB0",
        "outdoor_battery",
        30,
        {"id": 1},
        SENSOR_TYPES["battery"],
    )
    expiration_trigger = MagicMock()

    assert sensor.native_value is None
    assert sensor.icon == "mdi:battery-unknown"

    with (
        patch(
            "homeassistant.components.lacrosse.sensor.async_track_point_in_utc_time",
            return_value=expiration_trigger,
        ) as mock_track_expiration,
        patch.object(hass, "add_job"),
    ):
        sensor._callback_lacrosse(
            MagicMock(
                temperature=21.5, humidity=54, low_battery=False, new_battery=True
            ),
            None,
        )
        sensor._callback_lacrosse(
            MagicMock(
                temperature=21.5, humidity=54, low_battery=True, new_battery=False
            ),
            None,
        )

    assert mock_track_expiration.call_count == 2
    expiration_trigger.assert_called_once()
    assert sensor.native_value == "low"
    assert sensor.icon == "mdi:battery-alert"

    sensor._sensor_data.low_battery = False

    assert sensor.native_value == "ok"
    assert sensor.icon == "mdi:battery"

    with patch.object(sensor, "async_write_ha_state") as mock_write_state:
        sensor.value_is_expired()

    assert sensor._expiration_trigger is None
    mock_write_state.assert_called_once()
