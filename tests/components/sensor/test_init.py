"""The test for sensor entity."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pytest import approx

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_KPA,
    PRESSURE_MMHG,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.common import mock_restore_cache_with_extra_data


@pytest.mark.parametrize(
    "unit_system,native_unit,state_unit,native_value,state_value",
    [
        (IMPERIAL_SYSTEM, TEMP_FAHRENHEIT, TEMP_FAHRENHEIT, 100, 100),
        (IMPERIAL_SYSTEM, TEMP_CELSIUS, TEMP_FAHRENHEIT, 38, 100),
        (METRIC_SYSTEM, TEMP_FAHRENHEIT, TEMP_CELSIUS, 100, 38),
        (METRIC_SYSTEM, TEMP_CELSIUS, TEMP_CELSIUS, 38, 38),
    ],
)
async def test_temperature_conversion(
    hass,
    enable_custom_integrations,
    unit_system,
    native_unit,
    state_unit,
    native_value,
    state_value,
):
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
    assert float(state.state) == approx(float(state_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit


@pytest.mark.parametrize("device_class", (None, SensorDeviceClass.PRESSURE))
async def test_temperature_conversion_wrong_device_class(
    hass, device_class, enable_custom_integrations
):
    """Test temperatures are not converted if the sensor has wrong device class."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value="0.0",
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=device_class,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Check temperature is not converted
    state = hass.states.get(entity0.entity_id)
    assert state.state == "0.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_FAHRENHEIT


@pytest.mark.parametrize("state_class", ("measurement", "total_increasing"))
async def test_deprecated_last_reset(
    hass, caplog, enable_custom_integrations, state_class
):
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
        "to the custom integration author."
    ) in caplog.text

    state = hass.states.get("sensor.test")
    assert "last_reset" not in state.attributes


async def test_datetime_conversion(hass, caplog, enable_custom_integrations):
    """Test conversion of datetime."""
    test_timestamp = datetime(2017, 12, 19, 18, 29, 42, tzinfo=timezone.utc)
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


@pytest.mark.parametrize(
    "device_class,state_value,provides",
    [
        (SensorDeviceClass.DATE, "2021-01-09", "date"),
        (SensorDeviceClass.TIMESTAMP, "2021-01-09T12:00:00+00:00", "datetime"),
    ],
)
async def test_deprecated_datetime_str(
    hass, caplog, enable_custom_integrations, device_class, state_value, provides
):
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
    hass, caplog, enable_custom_integrations
):
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
    "str": {"native_unit_of_measurement": "°F", "native_value": "abc123"},
    "int": {"native_unit_of_measurement": "°F", "native_value": 123},
    "float": {"native_unit_of_measurement": "°F", "native_value": 123.0},
    "date": {
        "native_unit_of_measurement": "°F",
        "native_value": {
            "__type": "<class 'datetime.date'>",
            "isoformat": date(2020, 2, 8).isoformat(),
        },
    },
    "datetime": {
        "native_unit_of_measurement": "°F",
        "native_value": {
            "__type": "<class 'datetime.datetime'>",
            "isoformat": datetime(2020, 2, 8, 15, tzinfo=timezone.utc).isoformat(),
        },
    },
    "Decimal": {
        "native_unit_of_measurement": "°F",
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
    "native_value, native_value_type, expected_extra_data, device_class",
    [
        ("abc123", str, RESTORE_DATA["str"], None),
        (123, int, RESTORE_DATA["int"], SensorDeviceClass.TEMPERATURE),
        (123.0, float, RESTORE_DATA["float"], SensorDeviceClass.TEMPERATURE),
        (date(2020, 2, 8), dict, RESTORE_DATA["date"], SensorDeviceClass.DATE),
        (
            datetime(2020, 2, 8, 15, tzinfo=timezone.utc),
            dict,
            RESTORE_DATA["datetime"],
            SensorDeviceClass.TIMESTAMP,
        ),
        (Decimal("123.4"), dict, RESTORE_DATA["Decimal"], SensorDeviceClass.ENERGY),
    ],
)
async def test_restore_sensor_save_state(
    hass,
    enable_custom_integrations,
    hass_storage,
    native_value,
    native_value_type,
    expected_extra_data,
    device_class,
):
    """Test RestoreSensor."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockRestoreSensor(
        name="Test",
        native_value=native_value,
        native_unit_of_measurement=TEMP_FAHRENHEIT,
        device_class=device_class,
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    # Trigger saving state
    await hass.async_stop()

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == entity0.entity_id
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == expected_extra_data
    assert type(extra_data["native_value"]) == native_value_type


@pytest.mark.parametrize(
    "native_value, native_value_type, extra_data, device_class, uom",
    [
        ("abc123", str, RESTORE_DATA["str"], None, "°F"),
        (123, int, RESTORE_DATA["int"], SensorDeviceClass.TEMPERATURE, "°F"),
        (123.0, float, RESTORE_DATA["float"], SensorDeviceClass.TEMPERATURE, "°F"),
        (date(2020, 2, 8), date, RESTORE_DATA["date"], SensorDeviceClass.DATE, "°F"),
        (
            datetime(2020, 2, 8, 15, tzinfo=timezone.utc),
            datetime,
            RESTORE_DATA["datetime"],
            SensorDeviceClass.TIMESTAMP,
            "°F",
        ),
        (
            Decimal("123.4"),
            Decimal,
            RESTORE_DATA["Decimal"],
            SensorDeviceClass.ENERGY,
            "°F",
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
    hass,
    enable_custom_integrations,
    hass_storage,
    native_value,
    native_value_type,
    extra_data,
    device_class,
    uom,
):
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
    "device_class,native_unit,custom_unit,state_unit,native_value,custom_value",
    [
        # Smaller to larger unit, InHg is ~33x larger than hPa -> 1 more decimal
        (
            SensorDeviceClass.PRESSURE,
            PRESSURE_HPA,
            PRESSURE_INHG,
            PRESSURE_INHG,
            1000.0,
            29.53,
        ),
        (
            SensorDeviceClass.PRESSURE,
            PRESSURE_KPA,
            PRESSURE_HPA,
            PRESSURE_HPA,
            1.234,
            12.34,
        ),
        (
            SensorDeviceClass.PRESSURE,
            PRESSURE_HPA,
            PRESSURE_MMHG,
            PRESSURE_MMHG,
            1000,
            750,
        ),
        # Not a supported pressure unit
        (
            SensorDeviceClass.PRESSURE,
            PRESSURE_HPA,
            "peer_pressure",
            PRESSURE_HPA,
            1000,
            1000,
        ),
        (
            SensorDeviceClass.TEMPERATURE,
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
            TEMP_FAHRENHEIT,
            37.5,
            99.5,
        ),
        (
            SensorDeviceClass.TEMPERATURE,
            TEMP_FAHRENHEIT,
            TEMP_CELSIUS,
            TEMP_CELSIUS,
            100,
            38.0,
        ),
    ],
)
async def test_custom_unit(
    hass,
    enable_custom_integrations,
    device_class,
    native_unit,
    custom_unit,
    state_unit,
    native_value,
    custom_value,
):
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

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == approx(float(custom_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit


@pytest.mark.parametrize(
    "native_unit,custom_unit,state_unit,native_value,custom_value",
    [
        # Smaller to larger unit, InHg is ~33x larger than hPa -> 1 more decimal
        (PRESSURE_HPA, PRESSURE_INHG, PRESSURE_INHG, 1000.0, 29.53),
        (PRESSURE_KPA, PRESSURE_HPA, PRESSURE_HPA, 1.234, 12.34),
        (PRESSURE_HPA, PRESSURE_MMHG, PRESSURE_MMHG, 1000, 750),
        # Not a supported pressure unit
        (PRESSURE_HPA, "peer_pressure", PRESSURE_HPA, 1000, 1000),
    ],
)
async def test_custom_unit_change(
    hass,
    enable_custom_integrations,
    native_unit,
    custom_unit,
    state_unit,
    native_value,
    custom_value,
):
    """Test custom unit changes are picked up."""
    entity_registry = er.async_get(hass)
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        name="Test",
        native_value=str(native_value),
        native_unit_of_measurement=native_unit,
        device_class=SensorDeviceClass.PRESSURE,
        unique_id="very_unique",
    )

    entity0 = platform.ENTITIES["0"]
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == approx(float(native_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit

    entity_registry.async_update_entity_options(
        "sensor.test", "sensor", {"unit_of_measurement": custom_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == approx(float(custom_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == state_unit

    entity_registry.async_update_entity_options(
        "sensor.test", "sensor", {"unit_of_measurement": native_unit}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == approx(float(native_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit

    entity_registry.async_update_entity_options("sensor.test", "sensor", None)
    await hass.async_block_till_done()

    state = hass.states.get(entity0.entity_id)
    assert float(state.state) == approx(float(native_value))
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == native_unit
