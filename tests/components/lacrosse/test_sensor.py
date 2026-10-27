"""Tests for the LaCrosse sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.components.lacrosse.sensor import (
    PLATFORM_SCHEMA,
    LaCrosseBattery,
    LaCrosseHumidity,
    LaCrosseSensor,
    LaCrosseTemperature,
    _add_sensors,
    setup_platform,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "sensor_types",
    [
        pytest.param(("temperature",), id="temperature-only"),
        pytest.param(("humidity",), id="humidity-only"),
        pytest.param(("battery",), id="battery-only"),
        pytest.param(("temperature", "humidity"), id="temperature-humidity"),
        pytest.param(("temperature", "battery"), id="temperature-battery"),
        pytest.param(("humidity", "battery"), id="humidity-battery"),
        pytest.param(("temperature", "humidity", "battery"), id="all-types"),
    ],
)
async def test_import_creates_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_types: tuple[str, ...],
) -> None:
    """Test missing YAML measurements are registered but disabled."""
    with patch("homeassistant.components.lacrosse.pylacrosse.LaCrosse"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                "device": "/dev/ttyUSB0",
                "baud": 57600,
                "sensors": {
                    f"outdoor_{sensor_type}": {
                        "id": 1,
                        "type": sensor_type,
                        "name": "Outdoor",
                        "expire_after": 60,
                    }
                    for sensor_type in sensor_types
                },
            },
        )
        await hass.async_block_till_done()

    entry = result["result"]
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 3
    assert {entity.original_name for entity in entities} == {
        "Temperature",
        "Humidity",
        "Battery",
    }
    for sensor_type in sensor_types:
        entity = entity_registry.async_get(f"sensor.outdoor_{sensor_type}")
        assert entity is not None
        assert entity.disabled_by is None
        assert hass.states.get(entity.entity_id) is not None
    disabled = [entity for entity in entities if entity.disabled_by is not None]
    assert len(disabled) == 3 - len(sensor_types)
    assert all(
        entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for entity in disabled
    )
    assert all(hass.states.get(entity.entity_id) is None for entity in disabled)


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


def test_sensor_name_includes_sensor_type(hass: HomeAssistant) -> None:
    """Test a friendly name is combined with the sensor type."""
    added_sensors: list[LaCrosseSensor] = []
    _add_sensors(
        hass,
        MagicMock(),
        "receiver_entry_id",
        {
            "device": "/dev/ttyUSB0",
            "sensors": {
                "subentry_id_humidity": {
                    "id": 1,
                    "type": "humidity",
                    "name": "Test",
                }
            },
        },
        added_sensors.extend,
    )

    assert added_sensors[0].name == "Humidity"
    assert added_sensors[0].has_entity_name
    assert added_sensors[0].device_info["name"] == "Test"


@pytest.mark.parametrize(
    ("config", "device_name", "object_id"),
    [
        pytest.param(
            {"id": 1, "name": "Outdoor Patio"},
            "Outdoor Patio",
            "outdoor_patio",
            id="friendly-name",
        ),
        pytest.param(
            {"id": 1, "name": "  Outdoor-PATIO  "},
            "  Outdoor-PATIO  ",
            "outdoor_patio",
            id="formatted-name",
        ),
        pytest.param({"id": 2}, "LaCrosse sensor 2", "2", id="sensor-id-fallback"),
        pytest.param(
            {"id": 2, "name": ""},
            "LaCrosse sensor 2",
            "2",
            id="empty-name-fallback",
        ),
        pytest.param(
            {"id": 2, "name": "   "},
            "LaCrosse sensor 2",
            "2",
            id="blank-name-fallback",
        ),
    ],
)
@pytest.mark.parametrize("sensor_type", ["temperature", "humidity", "battery"])
def test_device_uses_name(
    hass: HomeAssistant,
    config: dict[str, str | int],
    device_name: str,
    object_id: str,
    sensor_type: str,
) -> None:
    """Test the entity ID is generated from the configured sensor key."""
    sensor_class = {
        "temperature": LaCrosseTemperature,
        "humidity": LaCrosseHumidity,
        "battery": LaCrosseBattery,
    }[sensor_type]
    sensor = sensor_class(
        hass,
        MagicMock(),
        "receiver_entry_id",
        "/dev/ttyUSB0",
        f"{object_id}_{sensor_type}",
        device_name,
        None,
        config,
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
    temperature = LaCrosseTemperature(
        hass,
        receiver,
        "receiver_entry_id",
        "/dev/ttyUSB0",
        "outdoor_temperature",
        "Outdoor temperature",
        None,
        config,
    )
    humidity = LaCrosseHumidity(
        hass,
        receiver,
        "receiver_entry_id",
        "/dev/ttyUSB0",
        "outdoor_humidity",
        "Outdoor humidity",
        None,
        config,
    )

    temperature._callback_lacrosse(sensor_data, None)
    humidity._callback_lacrosse(sensor_data, None)

    assert temperature.native_value == 21.5
    assert humidity.native_value == 54
    assert temperature.extra_state_attributes == {
        "low_battery": False,
        "new_battery": True,
    }


def test_sensor_registers_callback_when_created(hass: HomeAssistant) -> None:
    """Test receiver callbacks are registered when the entity is created."""
    receiver = MagicMock()
    sensor = LaCrosseSensor(
        hass,
        receiver,
        "receiver_entry_id",
        "/dev/ttyUSB0",
        "outdoor_temperature",
        "Outdoor temperature",
        None,
        {"id": 1},
    )

    assert sensor.should_poll is True
    receiver.register_callback.assert_called_once_with(
        1, sensor._callback_lacrosse, None
    )


async def test_sensor_cancels_expiration_when_removed(hass: HomeAssistant) -> None:
    """Test the expiration trigger is cancelled when the entity is removed."""
    sensor = LaCrosseSensor(
        hass,
        MagicMock(),
        "receiver_entry_id",
        "/dev/ttyUSB0",
        "outdoor_temperature",
        "Outdoor temperature",
        30,
        {"id": 1},
    )
    expiration_trigger = MagicMock()
    sensor._expiration_trigger = expiration_trigger

    await sensor.async_will_remove_from_hass()

    expiration_trigger.assert_called_once()
    assert sensor._expiration_trigger is None


@pytest.mark.parametrize(
    ("low_battery", "new_battery", "expected_value", "expected_icon"),
    [
        pytest.param(False, True, "ok", "mdi:battery", id="new"),
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
    sensor = LaCrosseBattery(
        hass,
        receiver,
        "receiver_entry_id",
        "/dev/ttyUSB0",
        "outdoor_battery",
        "Outdoor battery",
        30,
        {"id": 1},
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
    ):
        sensor._callback_lacrosse(sensor_data, None)
        sensor._callback_lacrosse(sensor_data, None)

    assert mock_track_expiration.call_count == 2
    expiration_trigger.assert_called_once()
    assert sensor.native_value == expected_value
    assert sensor.icon == expected_icon

    with patch.object(sensor, "async_write_ha_state") as mock_write_state:
        sensor.value_is_expired()

    assert sensor._expiration_trigger is None
    assert sensor.native_value == expected_value
    assert sensor.icon == expected_icon
    mock_write_state.assert_called_once()
