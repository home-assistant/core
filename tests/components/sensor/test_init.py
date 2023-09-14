"""The test for sensor entity."""
from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.sensor import (
    DEVICE_CLASS_STATE_CLASSES,
    DEVICE_CLASS_UNITS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    async_rounded_state,
    async_update_suggested_units,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    async_mock_restore_state_shutdown_restart,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache_with_extra_data,
)

TEST_DOMAIN = "test"


@pytest.mark.parametrize(
    ("unit_system", "native_unit", "state_unit", "native_value", "state_value"),
    [
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            100,
            "100",
        ),
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            38,
            "100",
        ),
        (
            METRIC_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
            100,
            "38",
        ),
        (
            METRIC_SYSTEM,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.CELSIUS,
            38,
            "38",
        ),
    ],
)
async def test_temperature_conversion(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    state_unit,
    native_value,
    state_value,
) -> None:
    """Test temperature conversion."""
    hass.config.units = unit_system
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=str(native_value),
        native_unit_of_measurement=native_unit,
        device_class=SensorDeviceClass.TEMPERATURE,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == state_value
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit


@pytest.mark.parametrize("device_class", (None, SensorDeviceClass.PRESSURE))
async def test_temperature_conversion_wrong_device_class(
    hass: HomeAssistant, device_class, enable_custom_integrations: None
) -> None:
    """Test temperatures are not converted if the sensor has wrong device class."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value="0.0",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=device_class,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Check temperature is not converted
    state = hass.states.get(entity0.entity_id)
    assert state.state == "0.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.FAHRENHEIT


@pytest.mark.parametrize("state_class", ("measurement", "total_increasing"))
async def test_deprecated_last_reset(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    state_class,
) -> None:
    """Test warning on deprecated last reset."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test", state_class=state_class, last_reset=dt_util.utc_from_timestamp(0)
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Entity sensor.test (<class 'custom_components.test.sensor.MockSensor'>) "
        f"with state_class {state_class} has set last_reset. Setting last_reset for "
        "entities with state_class other than 'total' is not supported. Please update "
        "your configuration if state_class is manually configured, otherwise report it "
        "to the custom integration author"
    ) in caplog.text

    state = hass.states.get("sensor.test")
    assert "last_reset" not in state.attributes


async def test_datetime_conversion(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test conversion of datetime."""
    test_timestamp = datetime(2017, 12, 19, 18, 29, 42, tzinfo=UTC)
    test_local_timestamp = test_timestamp.astimezone(
        dt_util.get_time_zone("Europe/Amsterdam")
    )
    test_date = date(2017, 12, 19)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=test_timestamp,
        device_class=SensorDeviceClass.TIMESTAMP,
    )
    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test", native_value=test_date, device_class=SensorDeviceClass.DATE
    )
    platform.ENTITIES["2"] = platform.MockSensor(
        name="Test", native_value=None, device_class=SensorDeviceClass.TIMESTAMP
    )
    platform.ENTITIES["3"] = platform.MockSensor(
        name="Test", native_value=None, device_class=SensorDeviceClass.DATE
    )
    platform.ENTITIES["4"] = platform.MockSensor(
        name="Test",
        native_value=test_local_timestamp,
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(platform.ENTITIES["0"].entity_id)
    assert state.state == test_timestamp.isoformat()

    state = hass.states.get(platform.ENTITIES["1"].entity_id)
    assert state.state == test_date.isoformat()

    state = hass.states.get(platform.ENTITIES["2"].entity_id)
    assert state.state == STATE_UNKNOWN

    state = hass.states.get(platform.ENTITIES["3"].entity_id)
    assert state.state == STATE_UNKNOWN

    state = hass.states.get(platform.ENTITIES["4"].entity_id)
    assert state.state == test_timestamp.isoformat()


async def test_a_sensor_with_a_non_numeric_device_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test that a sensor with a non numeric device class will be non numeric.

    A non numeric sensor with a valid device class should never be
    handled as numeric because it has a device class.
    """
    test_timestamp = datetime(2017, 12, 19, 18, 29, 42, tzinfo=UTC)
    test_local_timestamp = test_timestamp.astimezone(
        dt_util.get_time_zone("Europe/Amsterdam")
    )

    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=test_local_timestamp,
        native_unit_of_measurement="",
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test",
        native_value=test_local_timestamp,
        state_class="",
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(platform.ENTITIES["0"].entity_id)
    assert state.state == test_timestamp.isoformat()

    state = hass.states.get(platform.ENTITIES["1"].entity_id)
    assert state.state == test_timestamp.isoformat()


@pytest.mark.parametrize(
    ("device_class", "state_value", "provides"),
    [
        (SensorDeviceClass.DATE, "2021-01-09", "date"),
        (SensorDeviceClass.TIMESTAMP, "2021-01-09T12:00:00+00:00", "datetime"),
    ],
)
async def test_deprecated_datetime_str(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    device_class,
    state_value,
    provides,
) -> None:
    """Test warning on deprecated str for a date(time) value."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test", native_value=state_value, device_class=device_class
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        f"Invalid {provides}: sensor.test has {device_class} device class "
        f"but provides state {state_value}:{type(state_value)}"
    ) in caplog.text


async def test_reject_timezoneless_datetime_str(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test rejection of timezone-less datetime objects as timestamp."""
    test_timestamp = datetime(2017, 12, 19, 18, 29, 42, tzinfo=None)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=test_timestamp,
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Invalid datetime: sensor.test provides state '2017-12-19 18:29:42', "
        "which is missing timezone information"
    ) in caplog.text


RESTORE_DATA = {
    "str": {"native_unit_of_measurement": None, "native_value": "abc123"},
    "int": {"native_unit_of_measurement": "°F", "native_value": 123},
    "float": {"native_unit_of_measurement": "°F", "native_value": 123.0},
    "date": {
        "native_unit_of_measurement": None,
        "native_value": {
            "__type": "<class 'datetime.date'>",
            "isoformat": date(2020, 2, 8).isoformat(),
        },
    },
    "datetime": {
        "native_unit_of_measurement": None,
        "native_value": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2020, 2, 8, 15, tzinfo=UTC).isoformat(),
        },
    },
    "Decimal": {
        "native_unit_of_measurement": "kWh",
        "native_value": {
            "__type": "<class 'decimal.Decimal'>",
            "decimal_str": "123.4",
        },
    },
    "BadDecimal": {
        "native_unit_of_measurement": "°F",
        "native_value": {
            "__type": "<class 'decimal.Decimal'>",
            "decimal_str": "123f",
        },
    },
}


# None | str | int | float | date | datetime | Decimal:
@pytest.mark.parametrize(
    ("native_value", "native_value_type", "expected_extra_data", "device_class", "uom"),
    [
        ("abc123", str, RESTORE_DATA["str"], None, None),
        (
            123,
            int,
            RESTORE_DATA["int"],
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
        ),
        (
            123.0,
            float,
            RESTORE_DATA["float"],
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
        ),
        (date(2020, 2, 8), dict, RESTORE_DATA["date"], SensorDeviceClass.DATE, None),
        (
            datetime(2020, 2, 8, 15, tzinfo=UTC),
            dict,
            RESTORE_DATA["datetime"],
            SensorDeviceClass.TIMESTAMP,
            None,
        ),
        (
            Decimal("123.4"),
            dict,
            RESTORE_DATA["Decimal"],
            SensorDeviceClass.ENERGY,
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
    ],
)
async def test_restore_sensor_save_state(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    hass_storage: dict[str, Any],
    native_value,
    native_value_type,
    expected_extra_data,
    device_class,
    uom,
) -> None:
    """Test RestoreSensor."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockRestoreSensor(
        name="Test",
        native_value=native_value,
        native_unit_of_measurement=uom,
        device_class=device_class,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Trigger saving state
    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == entity0.entity_id
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == expected_extra_data
    assert type(extra_data["native_value"]) == native_value_type


@pytest.mark.parametrize(
    ("native_value", "native_value_type", "extra_data", "device_class", "uom"),
    [
        ("abc123", str, RESTORE_DATA["str"], None, None),
        (123, int, RESTORE_DATA["int"], SensorDeviceClass.TEMPERATURE, "°F"),
        (123.0, float, RESTORE_DATA["float"], SensorDeviceClass.TEMPERATURE, "°F"),
        (date(2020, 2, 8), date, RESTORE_DATA["date"], SensorDeviceClass.DATE, None),
        (
            datetime(2020, 2, 8, 15, tzinfo=UTC),
            datetime,
            RESTORE_DATA["datetime"],
            SensorDeviceClass.TIMESTAMP,
            None,
        ),
        (
            Decimal("123.4"),
            Decimal,
            RESTORE_DATA["Decimal"],
            SensorDeviceClass.ENERGY,
            "kWh",
        ),
        (None, type(None), None, None, None),
        (None, type(None), {}, None, None),
        (None, type(None), {"beer": 123}, None, None),
        (
            None,
            type(None),
            {"native_unit_of_measurement": "°F", "native_value": {}},
            None,
            None,
        ),
        (None, type(None), RESTORE_DATA["BadDecimal"], SensorDeviceClass.ENERGY, None),
    ],
)
async def test_restore_sensor_restore_state(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    hass_storage: dict[str, Any],
    native_value,
    native_value_type,
    extra_data,
    device_class,
    uom,
) -> None:
    """Test RestoreSensor."""
    mock_restore_cache_with_extra_data(hass, ((State("sensor.test", ""), extra_data),))

    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockRestoreSensor(
        name="Test",
        device_class=device_class,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert hass.states.get(entity0.entity_id)

    assert entity0.native_value == native_value
    assert type(entity0.native_value) == native_value_type
    assert entity0.native_unit_of_measurement == uom


@pytest.mark.parametrize(
    (
        "device_class",
        "native_unit",
        "custom_unit",
        "state_unit",
        "native_value",
        "custom_state",
    ),
    [
        # Smaller to larger unit, InHg is ~33x larger than hPa -> 1 more decimal
        (
            SensorDeviceClass.PRESSURE,
            UnitOfPressure.HPA,
            UnitOfPressure.INHG,
            UnitOfPressure.INHG,
            1000.0,
            "29.53",
        ),
        (
            SensorDeviceClass.PRESSURE,
            UnitOfPressure.KPA,
            UnitOfPressure.HPA,
            UnitOfPressure.HPA,
            1.234,
            "12.340",
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.HPA,
            UnitOfPressure.MMHG,
            UnitOfPressure.MMHG,
            1000,
            "750",
        ),
        (
            SensorDeviceClass.PRESSURE,
            UnitOfPressure.HPA,
            UnitOfPressure.MMHG,
            UnitOfPressure.MMHG,
            1000,
            "750",
        ),
        # Not a supported pressure unit
        (
            SensorDeviceClass.PRESSURE,
            UnitOfPressure.HPA,
            "peer_pressure",
            UnitOfPressure.HPA,
            1000,
            "1000",
        ),
        (
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.FAHRENHEIT,
            37.5,
            "99.5",
        ),
        (
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.CELSIUS,
            100,
            "38",
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.INHG,
            UnitOfPressure.HPA,
            UnitOfPressure.HPA,
            -0.00,
            "0.0",
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.INHG,
            UnitOfPressure.HPA,
            UnitOfPressure.HPA,
            -0.00001,
            "0",
        ),
    ],
)
async def test_custom_unit(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    device_class,
    native_unit,
    custom_unit,
    state_unit,
    native_value,
    custom_state,
) -> None:
    """Test custom unit."""
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get_or_create("sensor", "test", "very_unique")
    entity_registry.async_update_entity_options(
        entry.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=str(native_value),
        native_unit_of_measurement=native_unit,
        device_class=device_class,
        unique_id="very_unique",
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    entity_id = entity0.entity_id
    state = hass.states.get(entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit

    assert (
        async_rounded_state(hass, entity_id, hass.states.get(entity_id)) == custom_state
    )


@pytest.mark.parametrize(
    (
        "native_unit",
        "custom_unit",
        "state_unit",
        "native_value",
        "native_state",
        "custom_state",
        "device_class",
    ),
    [
        # Distance
        (
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
            UnitOfLength.MILES,
            1000,
            "1000",
            "621",
            SensorDeviceClass.DISTANCE,
        ),
        (
            UnitOfLength.CENTIMETERS,
            UnitOfLength.INCHES,
            UnitOfLength.INCHES,
            7.24,
            "7.24",
            "2.85",
            SensorDeviceClass.DISTANCE,
        ),
        (
            UnitOfLength.KILOMETERS,
            "peer_distance",
            UnitOfLength.KILOMETERS,
            1000,
            "1000",
            "1000",
            SensorDeviceClass.DISTANCE,
        ),
        # Energy
        (
            UnitOfEnergy.KILO_WATT_HOUR,
            UnitOfEnergy.MEGA_WATT_HOUR,
            UnitOfEnergy.MEGA_WATT_HOUR,
            1000,
            "1000",
            "1.000",
            SensorDeviceClass.ENERGY,
        ),
        (
            UnitOfEnergy.GIGA_JOULE,
            UnitOfEnergy.MEGA_WATT_HOUR,
            UnitOfEnergy.MEGA_WATT_HOUR,
            1000,
            "1000",
            "278",
            SensorDeviceClass.ENERGY,
        ),
        (
            UnitOfEnergy.KILO_WATT_HOUR,
            "BTU",
            UnitOfEnergy.KILO_WATT_HOUR,
            1000,
            "1000",
            "1000",
            SensorDeviceClass.ENERGY,
        ),
        # Power factor
        (
            None,
            PERCENTAGE,
            PERCENTAGE,
            1.0,
            "1.0",
            "100.0",
            SensorDeviceClass.POWER_FACTOR,
        ),
        (
            PERCENTAGE,
            None,
            None,
            100,
            "100",
            "1.00",
            SensorDeviceClass.POWER_FACTOR,
        ),
        (
            "Cos φ",
            None,
            "Cos φ",
            1.0,
            "1.0",
            "1.0",
            SensorDeviceClass.POWER_FACTOR,
        ),
        # Pressure
        # Smaller to larger unit, InHg is ~33x larger than hPa -> 1 more decimal
        (
            UnitOfPressure.HPA,
            UnitOfPressure.INHG,
            UnitOfPressure.INHG,
            1000.0,
            "1000.0",
            "29.53",
            SensorDeviceClass.PRESSURE,
        ),
        (
            UnitOfPressure.KPA,
            UnitOfPressure.HPA,
            UnitOfPressure.HPA,
            1.234,
            "1.234",
            "12.340",
            SensorDeviceClass.PRESSURE,
        ),
        (
            UnitOfPressure.HPA,
            UnitOfPressure.MMHG,
            UnitOfPressure.MMHG,
            1000,
            "1000",
            "750",
            SensorDeviceClass.PRESSURE,
        ),
        # Not a supported pressure unit
        (
            UnitOfPressure.HPA,
            "peer_pressure",
            UnitOfPressure.HPA,
            1000,
            "1000",
            "1000",
            SensorDeviceClass.PRESSURE,
        ),
        # Speed
        (
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            UnitOfSpeed.MILES_PER_HOUR,
            UnitOfSpeed.MILES_PER_HOUR,
            100,
            "100",
            "62",
            SensorDeviceClass.SPEED,
        ),
        (
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            78,
            "78",
            "0.13",
            SensorDeviceClass.SPEED,
        ),
        (
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            "peer_distance",
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            100,
            "100",
            "100",
            SensorDeviceClass.SPEED,
        ),
        # Volume
        (
            UnitOfVolume.CUBIC_METERS,
            UnitOfVolume.CUBIC_FEET,
            UnitOfVolume.CUBIC_FEET,
            100,
            "100",
            "3531",
            SensorDeviceClass.VOLUME,
        ),
        (
            UnitOfVolume.LITERS,
            UnitOfVolume.FLUID_OUNCES,
            UnitOfVolume.FLUID_OUNCES,
            2.3,
            "2.3",
            "77.8",
            SensorDeviceClass.VOLUME,
        ),
        (
            UnitOfVolume.CUBIC_METERS,
            "peer_distance",
            UnitOfVolume.CUBIC_METERS,
            100,
            "100",
            "100",
            SensorDeviceClass.VOLUME,
        ),
        # Weight
        (
            UnitOfMass.GRAMS,
            UnitOfMass.OUNCES,
            UnitOfMass.OUNCES,
            100,
            "100",
            "3.5",
            SensorDeviceClass.WEIGHT,
        ),
        (
            UnitOfMass.OUNCES,
            UnitOfMass.GRAMS,
            UnitOfMass.GRAMS,
            78,
            "78",
            "2211",
            SensorDeviceClass.WEIGHT,
        ),
        (
            UnitOfMass.GRAMS,
            "peer_distance",
            UnitOfMass.GRAMS,
            100,
            "100",
            "100",
            SensorDeviceClass.WEIGHT,
        ),
    ],
)
async def test_custom_unit_change(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit,
    custom_unit,
    state_unit,
    native_value,
    native_state,
    custom_state,
    device_class,
) -> None:
    """Test custom unit changes are picked up."""
    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=str(native_value),
        native_unit_of_measurement=native_unit,
        device_class=device_class,
        unique_id="very_unique",
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == native_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == native_unit

    entity_registry.async_update_entity_options(
        "sensor.test", "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == custom_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == state_unit

    entity_registry.async_update_entity_options(
        "sensor.test", "sensor", {"unit_of_measurement": native_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == native_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == native_unit

    entity_registry.async_update_entity_options("sensor.test", "sensor", None)
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == native_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == native_unit


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "automatic_unit",
        "suggested_unit",
        "custom_unit",
        "native_value",
        "native_state",
        "automatic_state",
        "suggested_state",
        "custom_state",
        "device_class",
    ),
    [
        # Distance
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
            UnitOfLength.METERS,
            UnitOfLength.YARDS,
            1000,
            "1000",
            "621",
            "1000000",
            "1093613",
            SensorDeviceClass.DISTANCE,
        )
    ],
)
async def test_unit_conversion_priority(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    automatic_unit,
    suggested_unit,
    custom_unit,
    native_value,
    native_state,
    automatic_state,
    suggested_state,
    custom_state,
    device_class,
) -> None:
    """Test priority of unit conversion."""

    hass.config.units = unit_system

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
    )
    entity1 = platform.ENTITIES["1"]

    platform.ENTITIES["2"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_unit_of_measurement=suggested_unit,
        unique_id="very_unique_2",
    )
    entity2 = platform.ENTITIES["2"]

    platform.ENTITIES["3"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_unit_of_measurement=suggested_unit,
    )
    entity3 = platform.ENTITIES["3"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Registered entity -> Follow automatic unit conversion
    state = hass.states.get(entity0.entity_id)
    assert state.state == automatic_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == automatic_unit
    # Assert the automatic unit conversion is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.unit_of_measurement == automatic_unit
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": automatic_unit}
    }

    # Unregistered entity -> Follow native unit
    state = hass.states.get(entity1.entity_id)
    assert state.state == native_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit

    # Registered entity with suggested unit
    state = hass.states.get(entity2.entity_id)
    assert state.state == suggested_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity2.entity_id)
    assert entry.unit_of_measurement == suggested_unit
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": suggested_unit}
    }

    # Unregistered entity with suggested unit
    state = hass.states.get(entity3.entity_id)
    assert state.state == suggested_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit

    # Set a custom unit, this should have priority over the automatic unit conversion
    entity_registry.async_update_entity_options(
        entity0.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    entity_registry.async_update_entity_options(
        entity2.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity2.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "automatic_unit",
        "suggested_unit",
        "custom_unit",
        "suggested_precision",
        "native_value",
        "native_state",
        "automatic_state",
        "suggested_state",
        "custom_state",
        "device_class",
    ),
    [
        # Distance
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
            UnitOfLength.METERS,
            UnitOfLength.YARDS,
            2,
            1000,
            "1000",
            621.371,
            1000000,
            1093613,
            SensorDeviceClass.DISTANCE,
        ),
    ],
)
async def test_unit_conversion_priority_precision(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    automatic_unit,
    suggested_unit,
    custom_unit,
    suggested_precision,
    native_value,
    native_state,
    automatic_state,
    suggested_state,
    custom_state,
    device_class,
) -> None:
    """Test priority of unit conversion for sensors with suggested_display_precision."""

    hass.config.units = unit_system

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_display_precision=suggested_precision,
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_display_precision=suggested_precision,
    )
    entity1 = platform.ENTITIES["1"]

    platform.ENTITIES["2"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_display_precision=suggested_precision,
        suggested_unit_of_measurement=suggested_unit,
        unique_id="very_unique_2",
    )
    entity2 = platform.ENTITIES["2"]

    platform.ENTITIES["3"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_display_precision=suggested_precision,
        suggested_unit_of_measurement=suggested_unit,
    )
    entity3 = platform.ENTITIES["3"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Registered entity -> Follow automatic unit conversion
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(automatic_state)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == automatic_unit
    # Assert the automatic unit conversion is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.unit_of_measurement == automatic_unit
    assert entry.options == {
        "sensor": {"suggested_display_precision": 2},
        "sensor.private": {"suggested_unit_of_measurement": automatic_unit},
    }
    assert float(async_rounded_state(hass, entity0.entity_id, state)) == pytest.approx(
        round(automatic_state, 2)
    )

    # Unregistered entity -> Follow native unit
    state = hass.states.get(entity1.entity_id)
    assert state.state == native_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit

    # Registered entity with suggested unit
    state = hass.states.get(entity2.entity_id)
    assert float(state.state) == pytest.approx(suggested_state)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity2.entity_id)
    assert entry.unit_of_measurement == suggested_unit
    assert entry.options == {
        "sensor": {"suggested_display_precision": 2},
        "sensor.private": {"suggested_unit_of_measurement": suggested_unit},
    }

    # Unregistered entity with suggested unit
    state = hass.states.get(entity3.entity_id)
    assert float(state.state) == pytest.approx(suggested_state)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit

    # Set a custom unit, this should have priority over the automatic unit conversion
    entity_registry.async_update_entity_options(
        entity0.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(custom_state)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    entity_registry.async_update_entity_options(
        entity2.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity2.entity_id)
    assert float(state.state) == pytest.approx(custom_state)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    # Set a display_precision, this should have priority over suggested_display_precision
    entity_registry.async_update_entity_options(
        entity0.entity_id,
        "sensor",
        {"suggested_display_precision": 2, "display_precision": 4},
    )
    entry0 = entity_registry.async_get(entity0.entity_id)
    assert entry0.options["sensor"]["suggested_display_precision"] == 2
    assert entry0.options["sensor"]["display_precision"] == 4
    await hass.async_block_till_done()
    assert float(async_rounded_state(hass, entity0.entity_id, state)) == pytest.approx(
        round(custom_state, 4)
    )


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "original_unit",
        "suggested_unit",
        "native_value",
        "original_value",
        "device_class",
    ),
    [
        # Distance
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfLength.KILOMETERS,
            UnitOfLength.YARDS,
            UnitOfLength.METERS,
            1000,
            1093613,
            SensorDeviceClass.DISTANCE,
        ),
    ],
)
async def test_unit_conversion_priority_suggested_unit_change(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    original_unit,
    suggested_unit,
    native_value,
    original_value,
    device_class,
) -> None:
    """Test priority of unit conversion."""

    hass.config.units = unit_system

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    # Pre-register entities
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "very_unique", unit_of_measurement=original_unit
    )
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor.private",
        {"suggested_unit_of_measurement": original_unit},
    )
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "very_unique_2", unit_of_measurement=original_unit
    )
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor.private",
        {"suggested_unit_of_measurement": original_unit},
    )

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_unit_of_measurement=suggested_unit,
        unique_id="very_unique_2",
    )
    entity1 = platform.ENTITIES["1"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Registered entity -> Follow automatic unit conversion the first time the entity was seen
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(original_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == original_unit
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.unit_of_measurement == original_unit
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": original_unit},
    }

    # Registered entity -> Follow suggested unit the first time the entity was seen
    state = hass.states.get(entity1.entity_id)
    assert float(state.state) == pytest.approx(float(original_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == original_unit
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity1.entity_id)
    assert entry.unit_of_measurement == original_unit
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": original_unit},
    }


@pytest.mark.parametrize(
    (
        "native_unit_1",
        "native_unit_2",
        "suggested_unit",
        "native_value",
        "original_value",
        "device_class",
    ),
    [
        # Distance
        (
            UnitOfLength.KILOMETERS,
            UnitOfLength.METERS,
            UnitOfLength.KILOMETERS,
            1000000,
            1000,
            SensorDeviceClass.DISTANCE,
        ),
        # Energy
        (
            UnitOfEnergy.KILO_WATT_HOUR,
            UnitOfEnergy.WATT_HOUR,
            UnitOfEnergy.KILO_WATT_HOUR,
            1000000,
            1000,
            SensorDeviceClass.ENERGY,
        ),
    ],
)
async def test_unit_conversion_priority_suggested_unit_change_2(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    native_unit_1,
    native_unit_2,
    suggested_unit,
    native_value,
    original_value,
    device_class,
) -> None:
    """Test priority of unit conversion."""

    hass.config.units = METRIC_SYSTEM

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    # Pre-register entities
    entity_registry.async_get_or_create(
        "sensor", "test", "very_unique", unit_of_measurement=native_unit_1
    )
    entity_registry.async_get_or_create(
        "sensor", "test", "very_unique_2", unit_of_measurement=native_unit_1
    )

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit_2,
        native_value=str(native_value),
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit_2,
        native_value=str(native_value),
        suggested_unit_of_measurement=suggested_unit,
        unique_id="very_unique_2",
    )
    entity1 = platform.ENTITIES["1"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Registered entity -> Follow unit in entity registry
    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(original_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit_1
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.unit_of_measurement == native_unit_1
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": native_unit_1},
    }

    # Registered entity -> Follow unit in entity registry
    state = hass.states.get(entity1.entity_id)
    assert float(state.state) == pytest.approx(float(original_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit_1
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.unit_of_measurement == native_unit_1
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": native_unit_1},
    }


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "integration_suggested_precision",
        "options_suggested_precision",
        "native_value",
        "device_class",
        "extra_options",
    ),
    [
        # Distance
        (
            METRIC_SYSTEM,
            UnitOfLength.KILOMETERS,
            4,
            4,
            1000,
            SensorDeviceClass.DISTANCE,
            {},
        ),
        # Air pressure
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfPressure.HPA,
            0,
            1,
            1000,
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            {"sensor.private": {"suggested_unit_of_measurement": "inHg"}},
        ),
    ],
)
async def test_suggested_precision_option(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    integration_suggested_precision,
    options_suggested_precision,
    native_value,
    device_class,
    extra_options,
) -> None:
    """Test suggested precision is stored in the registry."""

    hass.config.units = unit_system

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_display_precision=integration_suggested_precision,
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Assert the suggested precision is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.options == extra_options | {
        "sensor": {"suggested_display_precision": options_suggested_precision}
    }


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "suggested_unit",
        "old_precision",
        "new_precision",
        "opt_precision",
        "native_value",
        "device_class",
        "extra_options",
    ),
    [
        # Distance
        (
            METRIC_SYSTEM,
            UnitOfLength.KILOMETERS,
            UnitOfLength.KILOMETERS,
            4,
            1,
            1,
            1000,
            SensorDeviceClass.DISTANCE,
            {},
        ),
        # Air pressure
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfPressure.HPA,
            UnitOfPressure.INHG,
            1,
            1,
            2,
            1000,
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            {"sensor.private": {"suggested_unit_of_measurement": "inHg"}},
        ),
    ],
)
async def test_suggested_precision_option_update(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    suggested_unit,
    old_precision,
    new_precision,
    opt_precision,
    native_value,
    device_class,
    extra_options,
) -> None:
    """Test suggested precision stored in the registry is updated."""

    hass.config.units = unit_system

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    # Pre-register entities
    entry = entity_registry.async_get_or_create("sensor", "test", "very_unique")
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor",
        {
            "suggested_display_precision": old_precision,
        },
    )
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor.private",
        {
            "suggested_unit_of_measurement": suggested_unit,
        },
    )

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_display_precision=new_precision,
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Assert the suggested precision is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.options == {
        "sensor": {
            "suggested_display_precision": opt_precision,
        },
        "sensor.private": {
            "suggested_unit_of_measurement": suggested_unit,
        },
    }


@pytest.mark.parametrize(
    (
        "unit_system",
        "native_unit",
        "original_unit",
        "native_value",
        "original_value",
        "device_class",
    ),
    [
        # Distance
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
            1000,
            621.0,
            SensorDeviceClass.DISTANCE,
        ),
        (
            US_CUSTOMARY_SYSTEM,
            UnitOfLength.METERS,
            UnitOfLength.MILES,
            1000000,
            621.371,
            SensorDeviceClass.DISTANCE,
        ),
    ],
)
async def test_unit_conversion_priority_legacy_conversion_removed(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system,
    native_unit,
    original_unit,
    native_value,
    original_value,
    device_class,
) -> None:
    """Test priority of unit conversion."""

    hass.config.units = unit_system

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    # Pre-register entities
    entity_registry.async_get_or_create(
        "sensor", "test", "very_unique", unit_of_measurement=original_unit
    )

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == pytest.approx(float(original_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == original_unit


def test_device_classes_aligned() -> None:
    """Make sure all number device classes are also available in SensorDeviceClass."""

    for device_class in NumberDeviceClass:
        assert hasattr(SensorDeviceClass, device_class.name)
        assert getattr(SensorDeviceClass, device_class.name).value == device_class.value


async def test_value_unknown_in_enumeration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test warning on invalid enum value."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value="invalid_option",
        device_class=SensorDeviceClass.ENUM,
        options=["option1", "option2"],
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Sensor sensor.test provides state value 'invalid_option', "
        "which is not in the list of options provided"
    ) in caplog.text


async def test_invalid_enumeration_entity_with_device_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test warning on entities that provide an enum with a device class."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=21,
        device_class=SensorDeviceClass.POWER,
        options=["option1", "option2"],
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Sensor sensor.test is providing enum options, but has device class 'power' "
        "instead of 'enum'"
    ) in caplog.text


async def test_invalid_enumeration_entity_without_device_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test warning on entities that provide an enum without a device class."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=21,
        options=["option1", "option2"],
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Sensor sensor.test is providing enum options, but is missing "
        "the enum device class"
    ) in caplog.text


@pytest.mark.parametrize(
    "device_class",
    (
        SensorDeviceClass.DATE,
        SensorDeviceClass.ENUM,
        SensorDeviceClass.TIMESTAMP,
    ),
)
async def test_non_numeric_device_class_with_unit_of_measurement(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    device_class: SensorDeviceClass,
) -> None:
    """Test error on numeric entities that provide an unit of measurement."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=None,
        device_class=device_class,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        options=["option1", "option2"],
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "Sensor sensor.test has a unit of measurement and thus indicating it has "
        f"a numeric value; however, it has the non-numeric device class: {device_class}"
    ) in caplog.text


@pytest.mark.parametrize(
    "device_class",
    (
        SensorDeviceClass.APPARENT_POWER,
        SensorDeviceClass.AQI,
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        SensorDeviceClass.BATTERY,
        SensorDeviceClass.CO,
        SensorDeviceClass.CO2,
        SensorDeviceClass.CURRENT,
        SensorDeviceClass.DATA_RATE,
        SensorDeviceClass.DATA_SIZE,
        SensorDeviceClass.DISTANCE,
        SensorDeviceClass.DURATION,
        SensorDeviceClass.ENERGY,
        SensorDeviceClass.FREQUENCY,
        SensorDeviceClass.GAS,
        SensorDeviceClass.HUMIDITY,
        SensorDeviceClass.ILLUMINANCE,
        SensorDeviceClass.IRRADIANCE,
        SensorDeviceClass.MOISTURE,
        SensorDeviceClass.NITROGEN_DIOXIDE,
        SensorDeviceClass.NITROGEN_MONOXIDE,
        SensorDeviceClass.NITROUS_OXIDE,
        SensorDeviceClass.OZONE,
        SensorDeviceClass.PH,
        SensorDeviceClass.PM1,
        SensorDeviceClass.PM10,
        SensorDeviceClass.PM25,
        SensorDeviceClass.POWER_FACTOR,
        SensorDeviceClass.POWER,
        SensorDeviceClass.PRECIPITATION_INTENSITY,
        SensorDeviceClass.PRECIPITATION,
        SensorDeviceClass.PRESSURE,
        SensorDeviceClass.REACTIVE_POWER,
        SensorDeviceClass.SIGNAL_STRENGTH,
        SensorDeviceClass.SOUND_PRESSURE,
        SensorDeviceClass.SPEED,
        SensorDeviceClass.SULPHUR_DIOXIDE,
        SensorDeviceClass.TEMPERATURE,
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        SensorDeviceClass.VOLTAGE,
        SensorDeviceClass.VOLUME,
        SensorDeviceClass.WATER,
        SensorDeviceClass.WEIGHT,
        SensorDeviceClass.WIND_SPEED,
    ),
)
async def test_device_classes_with_invalid_unit_of_measurement(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    device_class: SensorDeviceClass,
) -> None:
    """Test error when unit of measurement is not valid for used device class."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value="1.0",
        device_class=device_class,
        native_unit_of_measurement="INVALID!",
    )
    units = [
        str(unit) if unit else "no unit of measurement"
        for unit in DEVICE_CLASS_UNITS.get(device_class, set())
    ]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    assert (
        "is using native unit of measurement 'INVALID!' which is not a valid "
        f"unit for the device class ('{device_class}') it is using; "
        f"expected one of {units}"
    ) in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_class", "unit"),
    [
        (SensorDeviceClass.AQI, None, None),
        (None, SensorStateClass.MEASUREMENT, None),
        (None, None, UnitOfTemperature.CELSIUS),
    ],
)
@pytest.mark.parametrize(
    ("native_value", "problem"),
    [
        ("", "non-numeric"),
        ("abc", "non-numeric"),
        ("13.7.1", "non-numeric"),
        (datetime(2012, 11, 10, 7, 35, 1), "non-numeric"),
        (date(2012, 11, 10), "non-numeric"),
        ("inf", "non-finite"),
        (float("inf"), "non-finite"),
        ("nan", "non-finite"),
        (float("nan"), "non-finite"),
    ],
)
async def test_non_numeric_validation_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    native_value: Any,
    problem: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    unit: str | None,
) -> None:
    """Test error on expected numeric entities."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=native_value,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=state_class,
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state is None

    assert (
        "thus indicating it has a numeric value; "
        f"however, it has the {problem} value: '{native_value}'"
    ) in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_class", "unit", "precision"), ((None, None, None, 1),)
)
@pytest.mark.parametrize(
    ("native_value", "expected"),
    [
        ("abc", "abc"),
        ("13.7.1", "13.7.1"),
        (datetime(2012, 11, 10, 7, 35, 1), "2012-11-10 07:35:01"),
        (date(2012, 11, 10), "2012-11-10"),
    ],
)
async def test_non_numeric_validation_raise(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    native_value: Any,
    expected: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    unit: str | None,
    precision,
) -> None:
    """Test error on expected numeric entities."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        device_class=device_class,
        native_unit_of_measurement=unit,
        native_value=native_value,
        state_class=state_class,
        suggested_display_precision=precision,
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state is None

    assert ("Error adding entities for domain sensor with platform test") in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_class", "unit"),
    [
        (SensorDeviceClass.AQI, None, None),
        (None, SensorStateClass.MEASUREMENT, None),
        (None, None, UnitOfTemperature.CELSIUS),
    ],
)
@pytest.mark.parametrize(
    ("native_value", "expected"),
    [
        (13, "13"),
        (17.50, "17.5"),
        ("1e-05", "1e-05"),
        (Decimal(18.50), "18.5"),
        ("19.70", "19.70"),
        (None, STATE_UNKNOWN),
    ],
)
async def test_numeric_validation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    native_value: Any,
    expected: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    unit: str | None,
) -> None:
    """Test does not error on expected numeric entities."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=native_value,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=state_class,
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == expected

    assert (
        "thus indicating it has a numeric value; "
        f"however, it has the non-numeric value: {native_value}"
    ) not in caplog.text


async def test_numeric_validation_ignores_custom_device_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
) -> None:
    """Test does not error on expected numeric entities."""
    native_value = "Three elephants"
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=native_value,
        device_class="custom__deviceclass",
    )
    entity0 = platform.ENTITIES["0"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == "Three elephants"

    assert (
        "thus indicating it has a numeric value; "
        f"however, it has the non-numeric value: {native_value}"
    ) not in caplog.text


@pytest.mark.parametrize(
    "device_class",
    list(SensorDeviceClass),
)
async def test_device_classes_with_invalid_state_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    device_class: SensorDeviceClass,
) -> None:
    """Test error when unit of measurement is not valid for used device class."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=None,
        state_class="INVALID!",
        device_class=device_class,
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    classes = DEVICE_CLASS_STATE_CLASSES.get(device_class, set())
    one_of = ", ".join(f"'{value.value}'" for value in classes)
    expected = f"None or one of {one_of}" if classes else "None"

    assert (
        "is using state class 'INVALID!' which is impossible considering device "
        f"class ('{device_class}') it is using; "
        f"expected {expected}"
    ) in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_class",
        "native_unit_of_measurement",
        "suggested_precision",
        "is_numeric",
    ),
    [
        (SensorDeviceClass.ENUM, None, None, None, False),
        (SensorDeviceClass.DATE, None, None, None, False),
        (SensorDeviceClass.TIMESTAMP, None, None, None, False),
        ("custom", None, None, None, False),
        (SensorDeviceClass.POWER, None, "V", None, True),
        (None, SensorStateClass.MEASUREMENT, None, None, True),
        (None, None, PERCENTAGE, None, True),
        (None, None, None, None, False),
    ],
)
async def test_numeric_state_expected_helper(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_custom_integrations: None,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    native_unit_of_measurement: str | None,
    suggested_precision: int | None,
    is_numeric: bool,
) -> None:
    """Test numeric_state_expected helper."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=None,
        device_class=device_class,
        state_class=state_class,
        native_unit_of_measurement=native_unit_of_measurement,
        suggested_display_precision=suggested_precision,
    )

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    entity0 = platform.ENTITIES["0"]
    state = hass.states.get(entity0.entity_id)
    assert state is not None

    assert entity0._numeric_state_expected == is_numeric


@pytest.mark.parametrize(
    (
        "unit_system_1",
        "unit_system_2",
        "native_unit",
        "automatic_unit_1",
        "automatic_unit_2",
        "suggested_unit",
        "custom_unit",
        "native_value",
        "automatic_state_1",
        "automatic_state_2",
        "suggested_state",
        "custom_state",
        "device_class",
    ),
    [
        # Distance
        (
            US_CUSTOMARY_SYSTEM,
            METRIC_SYSTEM,
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
            UnitOfLength.KILOMETERS,
            UnitOfLength.METERS,
            UnitOfLength.YARDS,
            1000,
            "621",
            "1000",
            "1000000",
            "1093613",
            SensorDeviceClass.DISTANCE,
        ),
    ],
)
async def test_unit_conversion_update(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    unit_system_1,
    unit_system_2,
    native_unit,
    automatic_unit_1,
    automatic_unit_2,
    suggested_unit,
    custom_unit,
    native_value,
    automatic_state_1,
    automatic_state_2,
    suggested_state,
    custom_state,
    device_class,
) -> None:
    """Test suggested unit can be updated."""

    hass.config.units = unit_system_1

    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)

    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test 0",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        unique_id="very_unique",
    )
    entity0 = platform.ENTITIES["0"]

    platform.ENTITIES["1"] = platform.MockSensor(
        name="Test 1",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        unique_id="very_unique_1",
    )
    entity1 = platform.ENTITIES["1"]

    platform.ENTITIES["2"] = platform.MockSensor(
        name="Test 2",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_unit_of_measurement=suggested_unit,
        unique_id="very_unique_2",
    )
    entity2 = platform.ENTITIES["2"]

    platform.ENTITIES["3"] = platform.MockSensor(
        name="Test 3",
        device_class=device_class,
        native_unit_of_measurement=native_unit,
        native_value=str(native_value),
        suggested_unit_of_measurement=suggested_unit,
        unique_id="very_unique_3",
    )
    entity3 = platform.ENTITIES["3"]

    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Registered entity -> Follow automatic unit conversion
    state = hass.states.get(entity0.entity_id)
    assert state.state == automatic_state_1
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == automatic_unit_1
    # Assert the automatic unit conversion is stored in the registry
    entry = entity_registry.async_get(entity0.entity_id)
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": automatic_unit_1}
    }

    state = hass.states.get(entity1.entity_id)
    assert state.state == automatic_state_1
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == automatic_unit_1
    # Assert the automatic unit conversion is stored in the registry
    entry = entity_registry.async_get(entity1.entity_id)
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": automatic_unit_1}
    }

    # Registered entity with suggested unit
    state = hass.states.get(entity2.entity_id)
    assert state.state == suggested_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity2.entity_id)
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": suggested_unit}
    }

    state = hass.states.get(entity3.entity_id)
    assert state.state == suggested_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit
    # Assert the suggested unit is stored in the registry
    entry = entity_registry.async_get(entity3.entity_id)
    assert entry.options == {
        "sensor.private": {"suggested_unit_of_measurement": suggested_unit}
    }

    # Set a custom unit, this should have priority over the automatic unit conversion
    entity_registry.async_update_entity_options(
        entity0.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    entity_registry.async_update_entity_options(
        entity2.entity_id, "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity2.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    # Change unit system, states and units should be unchanged
    hass.config.units = unit_system_2
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    state = hass.states.get(entity1.entity_id)
    assert state.state == automatic_state_1
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == automatic_unit_1

    state = hass.states.get(entity2.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    state = hass.states.get(entity3.entity_id)
    assert state.state == suggested_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit

    # Update suggested unit
    async_update_suggested_units(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    state = hass.states.get(entity1.entity_id)
    assert state.state == automatic_state_2
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == automatic_unit_2

    state = hass.states.get(entity2.entity_id)
    assert state.state == custom_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == custom_unit

    state = hass.states.get(entity3.entity_id)
    assert state.state == suggested_state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == suggested_unit


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None, None, None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_name(hass: HomeAssistant) -> None:
    """Test sensor name."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(config_entry, SENSOR_DOMAIN)
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed sensor without device class -> no name
    entity1 = SensorEntity()
    entity1.entity_id = "sensor.test1"

    # Unnamed sensor with device class but has_entity_name False -> no name
    entity2 = SensorEntity()
    entity2.entity_id = "sensor.test2"
    entity2._attr_device_class = SensorDeviceClass.BATTERY

    # Unnamed sensor with device class and has_entity_name True -> named
    entity3 = SensorEntity()
    entity3.entity_id = "sensor.test3"
    entity3._attr_device_class = SensorDeviceClass.BATTERY
    entity3._attr_has_entity_name = True

    # Unnamed sensor with device class and has_entity_name True -> named
    entity4 = SensorEntity()
    entity4.entity_id = "sensor.test4"
    entity4.entity_description = SensorEntityDescription(
        "test",
        SensorDeviceClass.BATTERY,
        has_entity_name=True,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test stt platform via config entry."""
        async_add_entities([entity1, entity2, entity3, entity4])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{SENSOR_DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state.attributes == {}

    state = hass.states.get(entity2.entity_id)
    assert state.attributes == {"device_class": "battery"}

    state = hass.states.get(entity3.entity_id)
    assert state.attributes == {"device_class": "battery", "friendly_name": "Battery"}

    state = hass.states.get(entity4.entity_id)
    assert state.attributes == {"device_class": "battery", "friendly_name": "Battery"}


def test_async_rounded_state_unregistered_entity_is_passthrough(
    hass: HomeAssistant,
) -> None:
    """Test async_rounded_state on unregistered entity is passthrough."""
    hass.states.async_set("sensor.test", "1.004")
    state = hass.states.get("sensor.test")
    assert async_rounded_state(hass, "sensor.test", state) == "1.004"
    hass.states.async_set("sensor.test", "-0.0")
    state = hass.states.get("sensor.test")
    assert async_rounded_state(hass, "sensor.test", state) == "-0.0"


def test_async_rounded_state_registered_entity_with_display_precision(
    hass: HomeAssistant,
) -> None:
    """Test async_rounded_state on registered with display precision.

    The -0 should be dropped.
    """
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get_or_create("sensor", "test", "very_unique")
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor",
        {"suggested_display_precision": 2, "display_precision": 4},
    )
    entity_id = entry.entity_id
    hass.states.async_set(entity_id, "1.004")
    state = hass.states.get(entity_id)
    assert async_rounded_state(hass, entity_id, state) == "1.0040"
    hass.states.async_set(entity_id, "-0.0")
    state = hass.states.get(entity_id)
    assert async_rounded_state(hass, entity_id, state) == "0.0000"
