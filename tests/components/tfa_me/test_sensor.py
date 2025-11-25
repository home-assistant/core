"""Test the TFA.me integration: test of sensor.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tfa_me.const import DOMAIN, MEASUREMENT_TO_TRANSLATION_KEY
from homeassistant.components.tfa_me.sensor import TFAmeSensorEntity, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er


class FailingEntitiesError(Exception):
    """Custom exception for testing."""


async def test_async_setup_entry_raises_config_entry_not_ready(
    hass: HomeAssistant, tfa_me_mock_entry
) -> None:
    """Test setup raises ConfigEntryNotReady on error."""

    def failing_entities(*args, **kwargs):
        raise FailingEntitiesError("failing_entities")

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, tfa_me_mock_entry, failing_entities)


async def test_sensor_entity_properties(tfa_me_mock_coordinator) -> None:
    """Test properties of TFAmeSensorEntity."""
    entity = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a01234567",
        entity_id="sensor.a01234567_temperature",
    )

    # Test: unique_id, name, measurement_name, native_value (float), unit
    assert entity.unique_id == "sensor.a01234567_temperature"
    assert entity.translation_key == "temperature"
    assert entity.measurement_name == "temperature"
    assert float(entity.native_value) == 23.5
    assert entity.native_unit_of_measurement == "°C"

    # Attributes
    attrs = entity.extra_state_attributes
    assert attrs["sensor_name"] == "A01234567"
    assert attrs["measurement"] == "temperature"
    assert "timestamp" in attrs
    assert "icon" in attrs

    # Humidity
    entity2 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a6f169ad1",
        entity_id="sensor.a6f169ad1_humidity",
    )
    assert float(entity2.native_value) == 50.0

    # Rain value
    entity3 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffea",
        entity_id="sensor.a1fffffea_rain_rel",
    )
    assert float(entity3.init_measure_value) == 7.4
    assert float(entity3.native_value) == 0.0

    # Test rain 1 hour
    now = datetime.now().timestamp()
    entity4 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffea",
        entity_id="sensor.a1fffffea_rain_hour",
    )
    assert float(entity4.init_measure_value) == 7.4
    assert entity4.rain_history.max_age == 60 * 60
    assert float(entity4.native_value) == 0.0

    # Add a history for test
    entity4.rain_history.add_measurement(7.4, int(now) - 60)
    entity4.rain_history.add_measurement(8.0, int(now) - 30)
    entity4.rain_history.add_measurement(9.0, int(now))
    assert entity4.rain_history.get_oldest_and_newest() == (
        (7.4, int(now) - 60),
        (9.0, int(now)),
    )
    assert float(entity4.init_measure_value) == 7.4
    await entity4.async_update()
    assert float(entity4.native_value) == 1.6
    # remove value
    del tfa_me_mock_coordinator.data[entity.entity_id]["value"]
    assert float(entity4.native_value) == 1.6

    # Test rain 24 hour
    now = datetime.now().timestamp()
    entity_24 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffec",
        entity_id="sensor.a1fffffec_rain_24hours",
    )
    assert float(entity_24.init_measure_value) == 7.4
    assert entity_24.rain_history_24.max_age == (24 * 60 * 60)
    assert float(entity_24.native_value) == 0.0

    # Add a history for test
    entity_24.rain_history_24.add_measurement(7.4, int(now) - 60)
    entity_24.rain_history_24.add_measurement(8.0, int(now) - 30)
    entity_24.rain_history_24.add_measurement(9.0, int(now))
    assert entity_24.rain_history_24.get_oldest_and_newest() == (
        (7.4, int(now) - 60),
        (9.0, int(now)),
    )
    assert float(entity_24.init_measure_value) == 7.4
    await entity4.async_update()
    assert float(entity_24.native_value) == 1.6

    # Test rain 1 hour (value missing) part 2
    entity4b = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffeb",
        entity_id="sensor.a1fffffeb_rain_hour",
    )
    assert entity4b.measure_name == "rain_1_hour"

    entity5 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffea",
        entity_id="sensor.a1fffffea_rain_24hours",
    )
    assert float(entity5.init_measure_value) == 7.4
    assert float(entity5.native_value) == 0.0

    # Station barometric pressure
    entity6 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="057654321",
        entity_id="sensor.057654321_barometric_pressure",
    )
    assert float(entity6.native_value) == 1000.1
    # unit None
    tfa_me_mock_coordinator.data[entity.entity_id]["unit"] = None
    assert entity.native_unit_of_measurement is None
    # Remove unit
    del tfa_me_mock_coordinator.data[entity.entity_id]["unit"]
    assert entity.native_unit_of_measurement == ""

    # Station barometric pressure without "measurement"
    entity7 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="057654322",
        entity_id="sensor.057654322_barometric_pressure",
    )
    attrs = entity7.extra_state_attributes
    assert attrs == {}

    # Station barometric pressure without "unit"
    entity8 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="057654323",
        entity_id="sensor.057654323_barometric_pressure",
    )
    assert entity8.native_unit_of_measurement == ""


async def test_wind_sensor(tfa_me_mock_coordinator) -> None:
    """Test wind sensor."""
    entity = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffb",
        entity_id="sensor.a2ffffffb_wind_direction_deg",
    )
    assert entity.native_value == 180.0

    # Invalid sensor ID  & entity ID
    entity_2 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffa",
        entity_id="sensor.a2ffffffa_wind_direction_deg",
    )
    assert entity_2.native_value is None

    # Invalid native value
    entity_3 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffc",
        entity_id="sensor.a2ffffffc_wind_direction_deg",
    )
    assert entity_3.native_value is None

    # Value is old
    entity_4 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffc",
        entity_id="sensor.a2ffffffc_rssi",
    )
    assert entity_4.native_value is None
    # Wrong ID
    assert entity_4.get_timeout("xx") == 0


ICONS_FILE = Path("homeassistant/components/tfa_me/icons.json")


def load_icons():
    """Load the icons.json as dictionary."""
    return json.loads(ICONS_FILE.read_text(encoding="utf-8"))["entity"]["sensor"]


def generate_test_cases():
    """Produce all test cases for "default", "range" & "state"."""
    sensors = load_icons()
    cases = []

    for sensor_type, cfg in sensors.items():
        # Default icon
        default_icon = cfg.get("default")
        if default_icon:
            cases.append(
                (
                    sensor_type,
                    "default",
                    None,
                    default_icon,
                )
            )
        # Range table
        if "range" in cfg:
            for value, icon in cfg["range"].items():
                cases.append(
                    (
                        sensor_type,
                        "range",
                        value,
                        icon,
                    )
                )
        # State table
        if "state" in cfg:
            for state_value, icon in cfg["state"].items():
                cases.append(
                    (
                        sensor_type,
                        "state",
                        state_value,
                        icon,
                    )
                )

    return cases


@pytest.mark.parametrize(
    ("sensor_type", "table", "key", "expected_icon"),
    generate_test_cases(),
)
def test_icons_json(sensor_type, table, key, expected_icon) -> None:
    """Validate all icons defined in icons.json."""
    sensors = load_icons()
    cfg = sensors[sensor_type]

    if table == "default":
        assert cfg["default"] == expected_icon

    elif table == "range":
        assert cfg["range"][key] == expected_icon

    elif table == "state":
        assert cfg["state"][key] == expected_icon

    else:
        pytest.fail(f"Unknown icon table '{table}'")


# @pytest.mark.asyncio
async def test_async_update_triggers_refresh_err() -> None:
    """Test async_update()."""
    # Arrange
    mock_coordinator = AsyncMock()
    entity = TFAmeSensorEntity(mock_coordinator, "abc", "sensor.abc_temp")

    # Action
    await entity.async_update()

    # Assert
    mock_coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_added_sets_initialized_and_writes_labels_if_missing(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """Test that labels are set once if they do not exist."""
    ent_reg = er.async_get(hass)

    # Create registry entry without labels
    unique_id = "a0f169ad1_temperature"
    reg_entry = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=unique_id,
        suggested_object_id=unique_id,
    )
    entity_id = reg_entry.entity_id

    # Create entity
    tfa_me_mock_coordinator.name_with_station_id = True
    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator, sensor_id="a0f169ad1", entity_id=unique_id
    )
    ent.hass = hass
    ent.entity_id = entity_id
    ent._attr_labels = ["TFA.me", "Temperature"]

    # Asserts
    assert not getattr(ent, "_initialized_once", False)
    await ent.async_added_to_hass()
    assert ent._initialized_once is True

    # Read registry again and verify labels
    updated = ent_reg.async_get(entity_id)
    assert updated is not None
    # Labels are set and stored
    assert set(updated.labels or []) == {"TFA.me", "Temperature"}


@pytest.mark.asyncio
async def test_async_added_does_not_overwrite_existing_labels(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """Test that labels are overwritten if they were set before."""
    ent_reg = er.async_get(hass)

    unique_id = "a0f169ad1_humidity"
    # Create registry entry with labels
    reg_entry = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=unique_id,
        suggested_object_id=unique_id,
    )
    entity_id = reg_entry.entity_id
    ent_reg.async_update_entity(entity_id, labels={"Existing", "Fix"})

    # Create entity
    tfa_me_mock_coordinator.name_with_station_id = True
    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator, sensor_id="a0f169ad1", entity_id=unique_id
    )
    ent.hass = hass
    ent.entity_id = entity_id
    ent._attr_labels = ["New", "Do_not_overwrite"]

    # Action
    await ent.async_added_to_hass()

    # Labels in registry are not changed
    updated = ent_reg.async_get(entity_id)
    assert updated is not None
    assert set(updated.labels or []) == {"Existing", "Fix"}


@pytest.mark.asyncio
async def test_async_added_returns_if_no_registry_entry(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """Test if ent_reg.async_get(...) returns None."""
    entity = TFAmeSensorEntity(tfa_me_mock_coordinator, "sensor1", "entity1")
    entity.hass = hass
    entity.entity_id = "sensor.tfa_me_1"
    entity._attr_labels = ["LabelA"]
    entity.name_with_station_id = True

    mock_reg = MagicMock()
    mock_reg.async_get.return_value = None  # Simulate: No registry entry

    with patch.object(er, "async_get", return_value=mock_reg) as mock_er_get:
        await entity.async_added_to_hass()

    # Assert: Registry function called
    assert mock_er_get.call_count == 1

    # Assert: The registry object was asked whether entity exists
    mock_reg.async_get.assert_called_once_with(entity.entity_id)

    # Assert: No update (return)
    mock_reg.async_update_entity.assert_not_called()

    # Entity initialized
    assert entity._initialized_once is True


@pytest.mark.parametrize(
    ("uid_suffix", "measurement", "raw_value", "expect_add"),
    [
        # rain_hour: valid -> add_measurement expected
        ("rain_hour", "rain_1_hour", "2.5", True),
        # rain_hour: error -> add_measurement NOT expected
        ("rain_hour", "rain_1_hour", "NOT_A_FLOAT", False),
        # rain_24hours: valid -> add_measurement expected
        ("rain_24hours", "rain_24_hours", "10.0", True),
        # rain_24hours: error -> add_measurement NOT expected
        ("rain_24hours", "rain_24_hours", "WRONG", False),
    ],
)
def test_handle_coordinator_update(
    hass: HomeAssistant,
    tfa_me_mock_coordinator,
    uid_suffix: str,
    measurement: str,
    raw_value: str,
    expect_add: bool,
) -> None:
    """Parametrized test for _handle_coordinator_update(), without cleanup()."""

    uid = f"sensor.017654321_a0f169ad1_{uid_suffix}"

    # Coordinator data entry the entity will read from
    sensor_data = {
        "gateway_id": "017654321",
        "sensor_name": "A1F169AD1",
        "timestamp": "2025-09-02T09:15:13Z",
        "ts": 1234567890,
        "measurement": measurement,
        "value": raw_value,
        "unit": "mm",
    }

    # Set data
    tfa_me_mock_coordinator.data = {uid: sensor_data}

    with (
        patch("homeassistant.components.tfa_me.sensor.SensorHistory") as mock_hist_cls,
        patch(
            "homeassistant.components.tfa_me.sensor.CoordinatorEntity._handle_coordinator_update"
        ),
    ):
        # SensorHistory mock instance used by the entity
        hist_mock = MagicMock()
        mock_hist_cls.return_value = hist_mock

        # Instantiate entity
        ent = TFAmeSensorEntity(
            tfa_me_mock_coordinator, sensor_id="a1f169ad1", entity_id=uid
        )
        ent.hass = hass

        # Ensure correct history attribute exists
        if measurement == "rain_1_hour":
            assert hasattr(ent, "rain_history")
        if measurement == "rain_24_hours":
            assert hasattr(ent, "rain_history_24")

        # Action: invoke update handler
        ent._handle_coordinator_update()

        # Expectation: add_measurement() called or not called
        if expect_add:
            hist_mock.add_measurement.assert_called_once_with(
                float(raw_value), 1234567890
            )
        else:
            hist_mock.add_measurement.assert_not_called()


@pytest.mark.asyncio
async def test_measurement_name_keyerror(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """Test measurement_name returns None when KeyError occurs."""

    uid = "sensor.017654321_a0f169ad1_temperature"

    # minimal example coordinator data
    tfa_me_mock_coordinator.data = {
        uid: {
            "sensor_id": "a0f169ad1",
            # "measurement": "temperature",   <-- intentionally removed
        }
    }

    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator,
        sensor_id="a0f169ad1",
        entity_id=uid,
    )
    ent.hass = hass

    # property access triggers KeyError in code → must return None
    assert ent.measurement_name is None


@pytest.mark.parametrize(
    ("measurement", "expected"),
    [
        (None, None),  # Case 1: measurement is None
        ("temperature", MEASUREMENT_TO_TRANSLATION_KEY.get("temperature")),  # mapped
        ("humidity", MEASUREMENT_TO_TRANSLATION_KEY.get("humidity")),  # mapped
        ("unknown_measure", "unknown_measure"),  # Case 3: not in mapping → return input
    ],
)
def test_get_translation_key(
    hass: HomeAssistant, tfa_me_mock_coordinator, measurement, expected
) -> None:
    """Test _get_translation_key with all possible branches."""

    # Create a dummy entity; the coordinator & other fields won't matter here.
    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator,
        sensor_id="a0f169ad1",
        entity_id="sensor.017654321_a0f169ad1_test",
    )

    result = ent._get_translation_key(measurement)
    assert result == expected


def test_native_value_generic_fallback(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """native_value should return data['value'] when no value_fn is defined and no timeout occurs."""

    # Build uid and coordinator data entry
    uid = "sensor.017654321_a0f169ad1_temperature"
    now_ts = int(datetime.now().timestamp())

    data_entry = {
        "gateway_id": "017654321",
        "sensor_name": "A0F169AD1",
        "timestamp": "2025-09-02T09:15:13Z",
        "ts": now_ts,  # fresh timestamp → no timeout
        "measurement": "temperature",
        "value": "42.5",  # this is what we expect to get back
        "unit": "°C",
    }

    tfa_me_mock_coordinator.data = {uid: data_entry}

    # Create entity
    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator, sensor_id="a0f169ad1", entity_id=uid
    )
    ent.hass = hass

    # Ensure timeout does NOT trigger: patch get_timeout to a large value
    ent.get_timeout = lambda _sensor_id: 999999  # effectively "no timeout" for the test

    # Provide an entity_description with value_fn = None
    ent.entity_description = SimpleNamespace(value_fn=None)

    # Action: access the property
    result = ent.native_value

    # Expectation: generic fallback is used → data.get("value")
    assert result == "42.5"
