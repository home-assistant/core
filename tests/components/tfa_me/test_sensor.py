"""Test the TFA.me integration: test of sensor.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"
# For snapshot: "pytest tests/components/tfa_me/test_sensor.py --snapshot-update"

from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tfa_me.const import (
    CONF_NAME_WITH_STATION_ID,
    DOMAIN,
    MEASUREMENT_TO_TRANSLATION_KEY,
)
from homeassistant.components.tfa_me.sensor import TFAmeSensorEntity, async_setup_entry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_JSON

from tests.common import MockConfigEntry, SnapshotAssertion


@pytest.mark.asyncio
async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """Test that async_setup_entry creates TFAmeSensorEntity instances for all coordinator data."""

    # Arrange: Fake config entry
    entry = MockConfigEntry(domain=DOMAIN, data={}, entry_id="test-entry-id")
    entry.add_to_hass(hass)

    # Fake coordinator with two sensors
    tfa_me_mock_coordinator.data = {
        "uid_1": {"sensor_id": "a204e4df6"},
        "uid_2": {"sensor_id": "a4481290f"},
    }

    # Put coordinator into hass.data as the setup function expects
    entry.runtime_data = tfa_me_mock_coordinator  # hass.data.setdefault(DOMAIN, {})[entry.entry_id] = tfa_me_mock_coordinator

    # Mock async_add_entities
    async_add_entities = MagicMock()

    # Act
    await async_setup_entry(hass, entry, async_add_entities)

    # Assert: async_add_entities was called once with a list of entities and update_before_add=True
    async_add_entities.assert_called_once()
    entities_arg, update_before_add = async_add_entities.call_args[0]

    assert update_before_add is True
    assert len(entities_arg) == 2

    # Check entity instances and that sensor_entity_list was updated
    assert all(isinstance(e, TFAmeSensorEntity) for e in entities_arg)
    assert sorted(tfa_me_mock_coordinator.sensor_entity_list) == ["uid_1", "uid_2"]


def _stable_state_dict(d: dict) -> dict:
    d = dict(d)  # shallow copy
    for k in ("last_changed", "last_updated", "last_reported", "context"):
        d.pop(k, None)
    return d


# pytest.mark.asyncio
async def test_tfa_me_sensor_entities_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all sensor entities created from a typical TFA.me JSON payload."""

    # 1) Create config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_NAME_WITH_STATION_ID: True,
        },
        title="TFA.me Station '05B3E4E44'",
    )
    entry.add_to_hass(hass)

    # 2) Patch HTTP client -> returns FAKE_JSON
    with patch(
        "homeassistant.components.tfa_me.coordinator.TFAmeClient.async_get_sensors",
        return_value=FAKE_JSON,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # 3) Collect all sensor entities from this config entry.
    ent_reg = er.async_get(hass)
    states: dict[str, dict] = {}

    for entity_id in sorted(hass.states.async_entity_ids("sensor")):
        ent = ent_reg.async_get(entity_id)
        # # Only entities from this config entry
        if not ent or ent.config_entry_id != entry.entry_id:
            continue

        state = hass.states.get(entity_id)
        states[entity_id] = _stable_state_dict(state.as_dict())
        # states[entity_id] = hass.states.get(entity_id).as_dict()

    # 4) Snapshot comparison
    assert states == snapshot


async def test_sensor_entity_properties(tfa_me_mock_coordinator) -> None:
    """Test temperature/himidity entities to get 100% code coverage of sensor.py."""
    entity = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a01234567",
        unique_id="sensor.017654321_a01234567_temperature",
    )

    # Test: unique_id, name, measurement_name, native_value (float), unit
    assert entity.unique_id == "sensor.017654321_a01234567_temperature"
    assert entity.translation_key == "temperature"
    assert entity.measurement_name == "temperature"
    assert float(entity.native_value) == 23.5
    assert entity.native_unit_of_measurement == "°C"

    # Station barometric pressure
    entity6 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="057654321",
        unique_id="sensor.017654321_017654321_barometric_pressure",
    )
    assert float(entity6.native_value) == 1000.1

    # Test: Unit None
    tfa_me_mock_coordinator.data[entity.entity_id]["unit"] = None
    assert entity.native_unit_of_measurement is None
    # Test: Remove unit
    del tfa_me_mock_coordinator.data[entity.entity_id]["unit"]
    assert entity.native_unit_of_measurement == ""

    # Station barometric pressure without "measurement"
    entity7 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="057654322",
        unique_id="sensor.017654321_a057654322_barometric_pressure",
    )
    attrs = entity7.extra_state_attributes
    assert attrs == {}


async def test_rain_sensor_entities(tfa_me_mock_coordinator) -> None:
    """Test rain entities to get 100% code coverage of sensor.py."""
    # Rain relative value
    entity3 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffea",
        unique_id="sensor.017654321_a1fffffea_rain_rel",
    )
    assert float(entity3.init_measure_value) == 7.4
    assert float(entity3.native_value) == 0.0

    # Test rain 1 hour
    entity4 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffea",
        unique_id="sensor.017654321_a1fffffea_rain_1_hour",
    )
    assert float(entity4.init_measure_value) == 7.4
    assert entity4.rain_history.max_age == 60 * 60
    assert float(entity4.native_value) == 0.0

    # Test rain 24 hour
    entity_24 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffec",
        unique_id="sensor.017654321_a1fffffec_rain_24_hours",
    )
    assert float(entity_24.init_measure_value) == 7.4
    assert entity_24.rain_history_24.max_age == (24 * 60 * 60)
    assert float(entity_24.native_value) == 0.0

    # Reset rain
    entity5 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a1fffffea",
        unique_id="sensor.017654321_a1fffffea_rain_24_hours",
    )
    assert float(entity5.init_measure_value) == 7.4
    assert float(entity5.native_value) == 0.0


async def test_wind_sensor(tfa_me_mock_coordinator) -> None:
    """Test wind sensor entities to get 100% code coverage of sensor.py."""
    entity = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffb",
        unique_id="sensor.017654321_a2ffffffb_wind_direction_deg",
    )
    assert entity.native_value == 180.0

    # Invalid native value
    entity_3 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffc",
        unique_id="sensor.017654321_a2ffffffc_wind_direction_deg",
    )
    assert entity_3.native_value is None

    # Value is old
    entity_4 = TFAmeSensorEntity(
        coordinator=tfa_me_mock_coordinator,
        sensor_id="a2ffffffc",
        unique_id="sensor.017654321_a2ffffffc_rssi",
    )
    assert entity_4.native_value is None
    # Test: Wrong ID
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


@pytest.mark.parametrize(
    ("uid_suffix", "measurement", "raw_value", "expect_add"),
    [
        # rain_1_hour: valid -> add_measurement expected
        ("rain_1_hour", "rain_1_hour", "2.5", True),
        # rain_1_hour: error -> add_measurement NOT expected
        ("rain_1_hour", "rain_1_hour", "NOT_A_FLOAT", False),
        # rain_24_hours: valid -> add_measurement expected
        ("rain_24_hours", "rain_24_hours", "10.0", True),
        # rain_24_hours: error -> add_measurement NOT expected
        ("rain_24_hours", "rain_24_hours", "WRONG", False),
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
            tfa_me_mock_coordinator, sensor_id="a1f169ad1", unique_id=uid
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

    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator,
        sensor_id="a0f169ad1",
        unique_id=None,  # uid, set invalid ID
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
        unique_id="sensor.017654321_a0f169ad1_test",
    )

    result = ent._get_translation_key(measurement)
    assert result == expected


def test_native_value_generic_fallback(
    hass: HomeAssistant, tfa_me_mock_coordinator
) -> None:
    """native_value should return data['value'] when no value_fn is defined and no timeout occurs."""

    # Build uid and coordinator data entry
    uid = "sensor.017654321_a01234567_temperature"
    # Create entity
    ent = TFAmeSensorEntity(
        tfa_me_mock_coordinator, sensor_id="a01234567", unique_id=uid
    )
    ent.hass = hass

    # Test: Timeout
    tfa_me_mock_coordinator.data[uid]["ts"] = 0
    assert ent.native_value is None

    # Provide an entity_description with value_fn = None
    ent.entity_description = SimpleNamespace(value_fn=None)
    tfa_me_mock_coordinator.data[uid]["ts"] = int(datetime.now().timestamp())

    # Test: generic fallback is used → data.get("value")
    assert ent.native_value == "23.5"
