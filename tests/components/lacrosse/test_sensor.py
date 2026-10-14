"""Tests for the LaCrosse sensor platform."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.components.lacrosse.sensor import (
    PLATFORM_SCHEMA,
    SENSOR_TYPES,
    LaCrosseSensor,
    _add_sensors,
    setup_platform,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant


async def test_setup_platform_imports_yaml_configuration(hass: HomeAssistant) -> None:
    """Test YAML configuration is imported through a config flow."""
    config = PLATFORM_SCHEMA({"platform": DOMAIN, "sensors": {}})
    assert "device" not in config

    with patch.object(
        hass.config_entries.flow, "async_init", new_callable=AsyncMock
    ) as mock_async_init:
        setup_platform(hass, config, MagicMock())
        await hass.async_block_till_done()

    mock_async_init.assert_awaited_once_with(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )


def test_sensor_uses_default_expiration(hass: HomeAssistant) -> None:
    """Test sensors expire after 300 seconds when not configured otherwise."""
    added_sensors: list[LaCrosseSensor] = []
    _add_sensors(
        hass,
        MagicMock(),
        {
            "device": "/dev/ttyUSB0",
            "sensors": {"outdoor": {"id": 1, "type": "temperature"}},
        },
        added_sensors.extend,
    )
    sensor = added_sensors[0]
    now = datetime(2024, 1, 1, tzinfo=UTC)

    with (
        patch(
            "homeassistant.components.lacrosse.sensor.dt_util.utcnow", return_value=now
        ),
        patch(
            "homeassistant.components.lacrosse.sensor.async_track_point_in_utc_time"
        ) as mock_track_expiration,
        patch.object(sensor, "async_write_ha_state"),
    ):
        sensor._async_handle_update(MagicMock())

    mock_track_expiration.assert_called_once_with(
        hass, sensor.value_is_expired, now + timedelta(seconds=300)
    )


@pytest.mark.parametrize(
    ("config", "device_name", "object_id"),
    [
        pytest.param(
            {"id": 1, "friendly_name": "Outdoor Patio"},
            "Outdoor Patio",
            "outdoor_patio",
            id="friendly-name",
        ),
        pytest.param(
            {"id": 1, "friendly_name": "  Outdoor-PATIO  "},
            "  Outdoor-PATIO  ",
            "outdoor_patio",
            id="formatted-name",
        ),
        pytest.param({"id": 2}, "LaCrosse sensor 2", "2", id="sensor-id-fallback"),
        pytest.param(
            {"id": 2, "friendly_name": ""},
            "LaCrosse sensor 2",
            "2",
            id="empty-name-fallback",
        ),
        pytest.param(
            {"id": 2, "friendly_name": "   "},
            "LaCrosse sensor 2",
            "2",
            id="blank-name-fallback",
        ),
    ],
)
@pytest.mark.parametrize("sensor_type", ["temperature", "humidity", "battery"])
def test_device_uses_friendly_name(
    hass: HomeAssistant,
    config: dict[str, str | int],
    device_name: str,
    object_id: str,
    sensor_type: str,
) -> None:
    """Test the entity ID is generated from the configured sensor key."""
    sensor = LaCrosseSensor(
        hass,
        MagicMock(),
        "/dev/ttyUSB0",
        f"{object_id}_{sensor_type}",
        None,
        config,
        SENSOR_TYPES[sensor_type],
    )

    assert sensor.device_info["name"] == device_name
    assert sensor.entity_id == f"sensor.{object_id}_{sensor_type}"


async def test_temperature_and_humidity_sensor_values(hass: HomeAssistant) -> None:
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

    with (
        patch.object(temperature, "async_write_ha_state") as mock_write_temperature,
        patch.object(humidity, "async_write_ha_state") as mock_write_humidity,
    ):
        temperature._callback_lacrosse(sensor_data, None)
        humidity._callback_lacrosse(sensor_data, None)
        await hass.async_block_till_done()

    assert temperature.native_value == 21.5
    assert humidity.native_value == 54
    assert temperature.extra_state_attributes == {
        "low_battery": False,
        "new_battery": True,
    }
    mock_write_temperature.assert_called_once()
    mock_write_humidity.assert_called_once()


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


async def test_sensor_cancels_expiration_when_removed(hass: HomeAssistant) -> None:
    """Test the expiration trigger is cancelled when the entity is removed."""
    sensor = LaCrosseSensor(
        hass,
        MagicMock(),
        "/dev/ttyUSB0",
        "outdoor_temperature",
        30,
        {"id": 1},
        SENSOR_TYPES["temperature"],
    )
    expiration_trigger = MagicMock()
    sensor._expiration_trigger = expiration_trigger

    await sensor.async_will_remove_from_hass()

    expiration_trigger.assert_called_once()
    assert sensor._expiration_trigger is None


@pytest.mark.parametrize(
    ("low_battery", "new_battery", "expected_value", "expected_icon"),
    [
        pytest.param(False, True, "new", "mdi:battery", id="new"),
        pytest.param(False, False, "ok", "mdi:battery", id="ok"),
        pytest.param(True, False, "low", "mdi:battery-alert", id="low"),
    ],
)
async def test_battery_sensor_updates_and_expires(
    hass: HomeAssistant,
    low_battery: bool,
    new_battery: bool,
    expected_value: str,
    expected_icon: str,
) -> None:
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
    sensor_data = MagicMock(
        temperature=21.5,
        humidity=54,
        low_battery=low_battery,
        new_battery=new_battery,
    )

    assert sensor.native_value is None
    assert sensor.icon == "mdi:battery-unknown"

    with (
        patch(
            "homeassistant.components.lacrosse.sensor.async_track_point_in_utc_time",
            return_value=expiration_trigger,
        ) as mock_track_expiration,
        patch.object(sensor, "async_write_ha_state") as mock_write_state,
    ):
        sensor._callback_lacrosse(sensor_data, None)
        sensor._callback_lacrosse(sensor_data, None)
        await hass.async_block_till_done()

    assert mock_track_expiration.call_count == 2
    expiration_trigger.assert_called_once()
    assert mock_write_state.call_count == 2
    assert sensor.native_value == expected_value
    assert sensor.icon == expected_icon

    with patch.object(sensor, "async_write_ha_state") as mock_write_state:
        sensor.value_is_expired()

    assert sensor._expiration_trigger is None
    assert sensor.native_value is None
    assert sensor.icon == "mdi:battery-unknown"
    mock_write_state.assert_called_once()
