"""Tests for the Bosch SHC sensor platform."""

from enum import Enum
from unittest.mock import MagicMock

from homeassistant.components.bosch_shc.const import (
    DOMAIN,
    OPT_DIAGNOSTIC_ENTITIES,
    OPT_EXCLUDED_DEVICES,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Fake enums (used instead of real lib enums to keep tests library-agnostic)
# ---------------------------------------------------------------------------


class _FakeRating(Enum):
    GOOD = "GOOD"
    MEDIUM = "MEDIUM"
    BAD = "BAD"


class _FakeWalkState(Enum):
    WALK_TEST_STARTED = "WALK_TEST_STARTED"
    WALK_TEST_STOPPED = "WALK_TEST_STOPPED"
    UNKNOWN = "UNKNOWN"


class _FakeDetectionState(Enum):
    DETECTION_TEST_STARTED = "DETECTION_TEST_STARTED"
    DETECTION_TEST_STOPPED = "DETECTION_TEST_STOPPED"
    DETECTION_TEST_UNKNOWN = "DETECTION_TEST_UNKNOWN"


class _FakeBatteryLevel(Enum):
    OK = "OK"
    LOW_BATTERY = "LOW_BATTERY"
    CRITICAL_LOW = "CRITICAL_LOW"
    CRITICALLY_LOW_BATTERY = "CRITICALLY_LOW_BATTERY"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class _FakeCommQuality(Enum):
    GOOD = "GOOD"
    MEDIUM = "MEDIUM"
    BAD = "BAD"


# ---------------------------------------------------------------------------
# Device factory helpers — each sets ALL attrs read by ALL platforms so that
# no MagicMock leaks into state serialization during NumberEntity / ValveEntity
# init (the min_offset / step_size problem).
#
# Pattern: build a defaults dict, update it with caller-supplied **extra, then
# call make_device once — this avoids "multiple values for keyword argument"
# when the caller overrides a default.
# ---------------------------------------------------------------------------


def make_thermostat(device_id="trv-1", name="Test TRV", **extra):
    """Thermostat device with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        # Sensor platform
        "temperature": 21.5,
        "position": 50,
        "valvestate": MagicMock(name="OPEN"),
        "supports_batterylevel": False,
        # Number platform (SHCNumber: Offset, and DisplayBrightness guarded by getattr)
        "offset": 0.5,
        "step_size": 0.5,
        "min_offset": -5.0,
        "max_offset": 5.0,
        "supports_display_configuration": False,
        # Switch platform — silentmode guarded by supports_silentmode
        "supports_silentmode": False,
        # Binary sensor platform — child_lock attr (ChildLock switch)
        "child_lock": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_wallthermostat(device_id="wt-1", name="Test WT", **extra):
    """Wallthermostat with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "temperature": 22.0,
        "humidity": 55.0,
        "supports_humidity": True,
        "terminal_temperature": None,
        "supports_batterylevel": False,
        # Number platform (same as thermostat)
        "offset": 0.5,
        "step_size": 0.5,
        "min_offset": -5.0,
        "max_offset": 5.0,
        "supports_display_configuration": False,
        "child_lock": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_roomthermostat(device_id="rth-1", name="Test RTH", **extra):
    """Room thermostat with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "temperature": 21.0,
        "humidity": 50.0,
        "supports_humidity": True,
        "terminal_temperature": None,
        "supports_batterylevel": False,
        "offset": 0.5,
        "step_size": 0.5,
        "min_offset": -5.0,
        "max_offset": 5.0,
        "supports_display_configuration": False,
        "child_lock": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_twinguard(device_id="tg-1", name="Test TG", **extra):
    """Twinguard with all cross-platform attrs pre-set."""
    combined_rating = MagicMock()
    combined_rating.name = "GOOD"
    temp_rating = MagicMock()
    temp_rating.name = "GOOD"
    hum_rating = MagicMock()
    hum_rating.name = "GOOD"
    purity_rating = MagicMock()
    purity_rating.name = "GOOD"
    defaults = {
        "status": "AVAILABLE",
        "temperature": 22.0,
        "humidity": 50.0,
        "purity": 500,
        "combined_rating": combined_rating,
        "temperature_rating": temp_rating,
        "humidity_rating": hum_rating,
        "purity_rating": purity_rating,
        "description": "Good air quality",
        "supports_humidity": True,
        "supports_batterylevel": False,
        # Select platform: smoke sensitivity guarded by getattr
        "supports_smoke_sensitivity": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_smart_plug(device_id="plug-1", name="Test Plug", **extra):
    """Smart plug with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "powerconsumption": 100.0,
        "energyconsumption": 1000000,
        "supports_energy_yield": False,
        # Switch platform: routing and energy_saving_mode guarded by getattr
        "supports_energy_saving_mode": False,
        "supports_power_switch_warning": False,
        "supports_power_switch_configuration": False,
        # Number platform: guarded by getattr
        "enter_duration_seconds": None,
        "supports_led_brightness": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_smart_plug_compact(device_id="spc-1", name="Test SPC", **extra):
    """Smart plug compact with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "powerconsumption": 50.0,
        "energyconsumption": 500000,
        "supports_energy_yield": False,
        "communicationquality": _FakeCommQuality.GOOD,
        "supports_energy_saving_mode": False,
        "supports_power_switch_configuration": False,
        "supports_led_brightness": False,
        "enter_duration_seconds": None,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_motion_detector(device_id="md-1", name="Test MD", **extra):
    """Motion detector with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "illuminance": 100,
        "supports_batterylevel": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_motion_detector2(device_id="md2-1", name="Test MD2", **extra):
    """Motion detector 2 with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "illuminance": 50,
        "temperature": 20.0,
        "supports_walk_test": False,
        "walk_state": None,
        "supports_detection_test": False,
        "supported_profiles": None,
        "supports_batterylevel": False,
        "communicationquality": _FakeCommQuality.GOOD,
        # Select platform: motion_sensitivity guarded by hasattr
        # Switch platform: pet_immunity guarded by getattr
        "supports_pet_immunity": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_shutter_contact2(device_id="sc2-1", name="Test SC2", **extra):
    """Shutter contact 2 with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "supports_batterylevel": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_light_switch_bsm(device_id="lsw-1", name="Test LSW", **extra):
    """Light switch BSM with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "powerconsumption": 60.0,
        "energyconsumption": 3600000,
        "supports_energy_yield": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_micromodule_shutter_control(device_id="msc-1", name="Test MSC", **extra):
    """Micromodule shutter control with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "powerconsumption": 25.0,
        "energyconsumption": 900000,
        "supports_energy_yield": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def make_micromodule_blinds(device_id="mb-1", name="Test MB", **extra):
    """Micromodule blinds with all cross-platform attrs pre-set."""
    defaults = {
        "status": "AVAILABLE",
        "powerconsumption": 10.0,
        "energyconsumption": 100000,
        "supports_energy_yield": False,
    }
    defaults.update(extra)
    return make_device(device_id=device_id, name=name, **defaults)


def _make_config_entry_with_options(mock_config_entry: MockConfigEntry, options: dict) -> MockConfigEntry:
    """Return a new MockConfigEntry that is a copy of mock_config_entry but with given options.

    This avoids the 'options cannot be changed directly' AttributeError from HA's
    immutable ConfigEntry.options setter; MockConfigEntry constructor accepts options=.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title=mock_config_entry.title,
        unique_id=mock_config_entry.unique_id,
        entry_id=mock_config_entry.entry_id,
        data=dict(mock_config_entry.data),
        options=options,
    )


# ---------------------------------------------------------------------------
# TemperatureSensor — from session.device_helper.thermostats
# ---------------------------------------------------------------------------


async def test_temperature_sensor_thermostat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TemperatureSensor is created for each thermostat device."""
    session = mock_setup_dependencies
    device = make_thermostat(
        device_id="trv-1",
        name="Living Room TRV",
        temperature=21.5,
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.living_room_trv_temperature")
    assert state is not None
    assert state.state == "21.5"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_valve_tappet_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ValveTappetSensor is created alongside TemperatureSensor for thermostats."""
    session = mock_setup_dependencies
    valve_state_mock = MagicMock()
    valve_state_mock.name = "OPEN"
    device = make_thermostat(
        device_id="trv-2",
        name="Bedroom TRV",
        temperature=19.0,
        position=75,
        valvestate=valve_state_mock,
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.bedroom_trv_valve_tappet")
    assert state is not None
    assert state.state == "75"
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["valve_tappet_state"] == "OPEN"


async def test_valve_tappet_sensor_disabled_when_diagnostic_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ValveTappetSensor is NOT created when OPT_DIAGNOSTIC_ENTITIES is False."""
    config_entry = _make_config_entry_with_options(
        mock_config_entry, {OPT_DIAGNOSTIC_ENTITIES: False}
    )
    session = mock_setup_dependencies
    device = make_thermostat(device_id="trv-3", name="Hall TRV", temperature=18.0)
    session.device_helper.thermostats = [device]

    await setup_integration(hass, config_entry)

    # TemperatureSensor must still appear
    assert hass.states.get("sensor.hall_trv_temperature") is not None
    # ValveTappetSensor must be absent
    assert hass.states.get("sensor.hall_trv_valve_tappet") is None


# ---------------------------------------------------------------------------
# TemperatureSensor + HumiditySensor — wallthermostats / roomthermostats
# ---------------------------------------------------------------------------


async def test_temperature_humidity_wallthermostats(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Wallthermostat devices get both Temperature and Humidity sensors."""
    session = mock_setup_dependencies
    device = make_wallthermostat(
        device_id="wt-1",
        name="Kitchen Thermostat",
        temperature=22.3,
        humidity=55.0,
    )
    session.device_helper.wallthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    temp_state = hass.states.get("sensor.kitchen_thermostat_temperature")
    assert temp_state is not None
    assert temp_state.state == "22.3"
    assert temp_state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE

    hum_state = hass.states.get("sensor.kitchen_thermostat_humidity")
    assert hum_state is not None
    assert hum_state.state == "55.0"
    assert hum_state.attributes["unit_of_measurement"] == PERCENTAGE
    assert hum_state.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert hum_state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_humidity_sensor_skipped_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HumiditySensor is skipped when supports_humidity is False."""
    session = mock_setup_dependencies
    device = make_wallthermostat(
        device_id="wt-2",
        name="Dry Thermostat",
        temperature=20.0,
        humidity=None,
        supports_humidity=False,
    )
    session.device_helper.wallthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.dry_thermostat_temperature") is not None
    assert hass.states.get("sensor.dry_thermostat_humidity") is None


async def test_terminal_temperature_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TerminalTemperatureSensor appears when terminal_temperature is not None."""
    session = mock_setup_dependencies
    device = make_roomthermostat(
        device_id="rth2-1",
        name="Floor Thermostat",
        temperature=21.0,
        humidity=50.0,
        terminal_temperature=18.5,
    )
    session.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    floor_state = hass.states.get("sensor.floor_thermostat_floor_temperature")
    assert floor_state is not None
    assert floor_state.state == "18.5"
    assert floor_state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert floor_state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


async def test_terminal_temperature_sensor_absent_when_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TerminalTemperatureSensor is NOT created when terminal_temperature is None."""
    session = mock_setup_dependencies
    device = make_roomthermostat(
        device_id="rth2-2",
        name="Room Thermostat Simple",
        supports_humidity=False,
        terminal_temperature=None,
    )
    session.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.room_thermostat_simple_floor_temperature") is None


# ---------------------------------------------------------------------------
# Twinguard sensors
# ---------------------------------------------------------------------------


async def test_twinguard_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Twinguard device creates Temperature, Humidity, Purity, AirQuality, and Rating sensors."""
    session = mock_setup_dependencies

    combined_rating = MagicMock()
    combined_rating.name = "GOOD"
    temp_rating = MagicMock()
    temp_rating.name = "GOOD"
    hum_rating = MagicMock()
    hum_rating.name = "MEDIUM"
    purity_rating = MagicMock()
    purity_rating.name = "BAD"

    device = make_twinguard(
        device_id="tg-1",
        name="Twinguard Living",
        temperature=23.1,
        humidity=48.0,
        purity=700,
        combined_rating=combined_rating,
        temperature_rating=temp_rating,
        humidity_rating=hum_rating,
        purity_rating=purity_rating,
        description="Good air quality",
        supports_batterylevel=True,
        batterylevel=_FakeBatteryLevel.OK,
    )
    air_service_mock = MagicMock()
    air_service_mock.comfortZone = "COMFORT"
    device._airqualitylevel_service = air_service_mock

    session.device_helper.twinguards = [device]

    await setup_integration(hass, mock_config_entry)

    temp = hass.states.get("sensor.twinguard_living_temperature")
    assert temp is not None
    assert temp.state == "23.1"

    hum = hass.states.get("sensor.twinguard_living_humidity")
    assert hum is not None
    assert hum.state == "48.0"
    assert hum.attributes["unit_of_measurement"] == PERCENTAGE

    purity = hass.states.get("sensor.twinguard_living_purity")
    assert purity is not None
    assert purity.state == "700"
    assert purity.attributes["unit_of_measurement"] == CONCENTRATION_PARTS_PER_MILLION
    assert purity.attributes["state_class"] == SensorStateClass.MEASUREMENT

    air_quality = hass.states.get("sensor.twinguard_living_air_quality")
    assert air_quality is not None
    assert air_quality.state == "GOOD"
    assert air_quality.attributes["rating_description"] == "Good air quality"
    assert air_quality.attributes["comfort_zone"] == "COMFORT"

    temp_rating_state = hass.states.get("sensor.twinguard_living_temperature_rating")
    assert temp_rating_state is not None
    assert temp_rating_state.state == "GOOD"

    hum_rating_state = hass.states.get("sensor.twinguard_living_humidity_rating")
    assert hum_rating_state is not None
    assert hum_rating_state.state == "MEDIUM"

    purity_rating_state = hass.states.get("sensor.twinguard_living_purity_rating")
    assert purity_rating_state is not None
    assert purity_rating_state.state == "BAD"


async def test_twinguard_diagnostic_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Twinguard creates CombinedRating and Description diagnostic sensors when diagnostics enabled."""
    session = mock_setup_dependencies

    combined_rating = MagicMock()
    combined_rating.name = "MEDIUM"

    device = make_twinguard(
        device_id="tg-2",
        name="Twinguard Office",
        temperature=22.0,
        humidity=55.0,
        purity=500,
        combined_rating=combined_rating,
        temperature_rating=combined_rating,
        humidity_rating=combined_rating,
        purity_rating=combined_rating,
        description="Average air quality",
    )
    session.device_helper.twinguards = [device]

    await setup_integration(hass, mock_config_entry)

    combined = hass.states.get("sensor.twinguard_office_combined_rating")
    assert combined is not None
    assert combined.state == "MEDIUM"
    assert combined.attributes.get("device_class") == SensorDeviceClass.ENUM

    desc = hass.states.get("sensor.twinguard_office_air_quality_description")
    assert desc is not None
    assert desc.state == "Average air quality"


async def test_twinguard_diagnostic_sensors_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Twinguard does NOT create CombinedRating and Description sensors when diagnostics disabled."""
    config_entry = _make_config_entry_with_options(
        mock_config_entry, {OPT_DIAGNOSTIC_ENTITIES: False}
    )
    session = mock_setup_dependencies

    combined_rating = MagicMock()
    combined_rating.name = "GOOD"

    device = make_twinguard(
        device_id="tg-3",
        name="Twinguard Bedroom",
        temperature=21.0,
        humidity=45.0,
        purity=400,
        combined_rating=combined_rating,
        temperature_rating=combined_rating,
        humidity_rating=combined_rating,
        purity_rating=combined_rating,
        description="Good",
    )
    session.device_helper.twinguards = [device]

    await setup_integration(hass, config_entry)

    assert hass.states.get("sensor.twinguard_bedroom_combined_rating") is None
    assert hass.states.get("sensor.twinguard_bedroom_air_quality_description") is None


async def test_twinguard_air_quality_no_comfort_zone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """AirQualitySensor extra_state_attributes omits comfort_zone when service absent."""
    session = mock_setup_dependencies

    combined_rating = MagicMock()
    combined_rating.name = "GOOD"

    device = make_twinguard(
        device_id="tg-4",
        name="Twinguard Hallway",
        temperature=20.0,
        humidity=50.0,
        purity=600,
        combined_rating=combined_rating,
        temperature_rating=combined_rating,
        humidity_rating=combined_rating,
        purity_rating=combined_rating,
        description="Good",
    )
    # No _airqualitylevel_service attribute — suppress MagicMock auto-create
    # by deleting it if the MagicMock created one, then set to None
    device._airqualitylevel_service = None
    session.device_helper.twinguards = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.twinguard_hallway_air_quality")
    assert state is not None
    assert "comfort_zone" not in state.attributes


# ---------------------------------------------------------------------------
# Power / Energy sensors — smart_plugs
# ---------------------------------------------------------------------------


async def test_power_sensor_smart_plug(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PowerSensor is created for smart plug devices."""
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-1",
        name="Coffee Maker",
        powerconsumption=1200.5,
        energyconsumption=5000000,
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    power = hass.states.get("sensor.coffee_maker_power")
    assert power is not None
    assert power.state == "1200.5"
    assert power.attributes["unit_of_measurement"] == UnitOfPower.WATT
    assert power.attributes["device_class"] == SensorDeviceClass.POWER
    assert power.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_energy_sensor_smart_plug(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """EnergySensor converts Wh to kWh for smart plug devices."""
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-2",
        name="Washing Machine",
        powerconsumption=500.0,
        energyconsumption=2000000,  # 2000 kWh in Wh
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    energy = hass.states.get("sensor.washing_machine_energy")
    assert energy is not None
    assert energy.state == "2000.0"
    assert energy.attributes["unit_of_measurement"] == UnitOfEnergy.KILO_WATT_HOUR
    assert energy.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert energy.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING


async def test_energy_sensor_none_energyconsumption(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """EnergySensor returns None state when energyconsumption is None."""
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-3",
        name="Unknown Plug",
        powerconsumption=0.0,
        energyconsumption=None,
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.unknown_plug_energy")
    assert state is not None
    assert state.state == "unknown"


async def test_energy_yield_and_power_yield_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """EnergyYieldSensor and PowerYieldSensor are created when supports_energy_yield=True."""
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-4",
        name="Solar Plug",
        powerconsumption=-300.0,  # negative = feeding grid
        energyconsumption=1000000,
        energy_yield=500000,  # 500 kWh in Wh
        supports_energy_yield=True,
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    energy_yield = hass.states.get("sensor.solar_plug_energy_yield")
    assert energy_yield is not None
    assert energy_yield.state == "500.0"
    assert energy_yield.attributes["unit_of_measurement"] == UnitOfEnergy.KILO_WATT_HOUR
    assert energy_yield.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert energy_yield.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING

    power_yield = hass.states.get("sensor.solar_plug_power_yield")
    assert power_yield is not None
    # powerconsumption=-300 → yield = 300 W positive
    assert power_yield.state == "300.0"
    assert power_yield.attributes["unit_of_measurement"] == UnitOfPower.WATT
    assert power_yield.attributes["device_class"] == SensorDeviceClass.POWER
    assert power_yield.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_power_yield_sensor_zero_when_consuming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PowerYieldSensor returns 0 when net-consuming (positive powerconsumption)."""
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-5",
        name="Consuming Plug",
        powerconsumption=150.0,
        energyconsumption=2000000,
        energy_yield=100000,
        supports_energy_yield=True,
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    power_yield = hass.states.get("sensor.consuming_plug_power_yield")
    assert power_yield is not None
    assert power_yield.state == "0.0"


async def test_energy_yield_sensor_none_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """EnergyYieldSensor returns unknown state when energy_yield is None."""
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-6",
        name="Minimal Solar Plug",
        powerconsumption=0.0,
        energyconsumption=0,
        energy_yield=None,
        supports_energy_yield=True,
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.minimal_solar_plug_energy_yield")
    assert state is not None
    assert state.state == "unknown"


# ---------------------------------------------------------------------------
# Smart Plug Compact — also has CommunicationQuality when diagnostics enabled
# ---------------------------------------------------------------------------


async def test_smart_plug_compact_communication_quality(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Smart plug compact creates CommunicationQualitySensor when diagnostic enabled."""
    session = mock_setup_dependencies
    device = make_smart_plug_compact(
        device_id="spc-1",
        name="Compact Plug",
        powerconsumption=50.0,
        energyconsumption=100000,
        communicationquality=_FakeCommQuality.GOOD,
    )
    session.device_helper.smart_plugs_compact = [device]

    await setup_integration(hass, mock_config_entry)

    comm = hass.states.get("sensor.compact_plug_communication_quality")
    assert comm is not None
    assert comm.state == "GOOD"


async def test_smart_plug_compact_no_communication_quality_when_diagnostic_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CommunicationQualitySensor not created for compact plug when diagnostics off."""
    config_entry = _make_config_entry_with_options(
        mock_config_entry, {OPT_DIAGNOSTIC_ENTITIES: False}
    )
    session = mock_setup_dependencies
    device = make_smart_plug_compact(
        device_id="spc-2",
        name="Compact Plug Diag Off",
        communicationquality=_FakeCommQuality.GOOD,
    )
    session.device_helper.smart_plugs_compact = [device]

    await setup_integration(hass, config_entry)

    assert hass.states.get("sensor.compact_plug_diag_off_communication_quality") is None


# ---------------------------------------------------------------------------
# Light switch BSM gets Power + Energy sensors
# ---------------------------------------------------------------------------


async def test_light_switch_bsm_power_and_energy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Light switch BSM devices get Power and Energy sensors."""
    session = mock_setup_dependencies
    device = make_light_switch_bsm(
        device_id="lsw-1",
        name="Living Room Light",
        powerconsumption=60.0,
        energyconsumption=3600000,
    )
    session.device_helper.light_switches_bsm = [device]

    await setup_integration(hass, mock_config_entry)

    power = hass.states.get("sensor.living_room_light_power")
    assert power is not None
    assert power.state == "60.0"

    energy = hass.states.get("sensor.living_room_light_energy")
    assert energy is not None
    assert energy.state == "3600.0"


# ---------------------------------------------------------------------------
# Motion Detector — IlluminanceLevelSensor
# ---------------------------------------------------------------------------


async def test_illuminance_sensor_motion_detector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """IlluminanceLevelSensor is created for motion detector devices."""
    session = mock_setup_dependencies
    device = make_motion_detector(
        device_id="md-1",
        name="Hallway Motion",
        illuminance=120,
        supports_batterylevel=True,
        batterylevel=_FakeBatteryLevel.OK,
    )
    session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.hallway_motion_illuminance")
    assert state is not None
    assert state.state == "120"
    assert state.attributes["unit_of_measurement"] == LIGHT_LUX
    assert state.attributes["device_class"] == SensorDeviceClass.ILLUMINANCE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_illuminance_sensor_bool_returns_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """IlluminanceLevelSensor returns unknown state when illuminance is a boolean."""
    session = mock_setup_dependencies
    device = make_motion_detector(
        device_id="md-2",
        name="Garage Motion",
        illuminance=True,  # boolean — should coerce to None
    )
    session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.garage_motion_illuminance")
    assert state is not None
    assert state.state == "unknown"


# ---------------------------------------------------------------------------
# Motion Detector 2 — Illuminance + Temperature + optional Walk/Detection/Profile
# ---------------------------------------------------------------------------


async def test_motion_detector2_basic_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MD2 gets Illuminance and Temperature sensors."""
    session = mock_setup_dependencies
    device = make_motion_detector2(
        device_id="md2-1",
        name="MD2 Kitchen",
        illuminance=45,
        temperature=20.5,
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    illuminance = hass.states.get("sensor.md2_kitchen_illuminance")
    assert illuminance is not None
    assert illuminance.state == "45"

    temp = hass.states.get("sensor.md2_kitchen_temperature")
    assert temp is not None
    assert temp.state == "20.5"


async def test_motion_detector2_walk_state_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MD2 with WalkTest creates WalkStateSensor."""
    session = mock_setup_dependencies
    walk_state_mock = _FakeWalkState.WALK_TEST_STOPPED
    device = make_motion_detector2(
        device_id="md2-2",
        name="MD2 Walk",
        illuminance=10,
        temperature=19.0,
        supports_walk_test=True,
        walk_state=walk_state_mock,
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.md2_walk_walk_test_state")
    assert state is not None
    assert state.state == "WALK_TEST_STOPPED"
    assert state.attributes.get("device_class") == SensorDeviceClass.ENUM


async def test_motion_detector2_walk_state_none_not_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """WalkStateSensor not created when walk_state is None (no WalkTest service)."""
    session = mock_setup_dependencies
    device = make_motion_detector2(
        device_id="md2-3",
        name="MD2 No Walk",
        supports_walk_test=True,
        walk_state=None,
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.md2_no_walk_walk_test_state") is None


async def test_motion_detector2_detection_state_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MD2 with DetectionTest creates DetectionStateSensor."""
    session = mock_setup_dependencies
    detection_state_mock = _FakeDetectionState.DETECTION_TEST_STOPPED
    device = make_motion_detector2(
        device_id="md2-4",
        name="MD2 Detection",
        illuminance=20,
        temperature=21.0,
        supports_detection_test=True,
        detection_state=detection_state_mock,
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.md2_detection_detection_test_state")
    assert state is not None
    assert state.state == "DETECTION_TEST_STOPPED"
    assert state.attributes.get("device_class") == SensorDeviceClass.ENUM


async def test_motion_detector2_installation_profile_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MD2 with supported_profiles creates InstallationProfileSensor."""
    session = mock_setup_dependencies
    device = make_motion_detector2(
        device_id="md2-5",
        name="MD2 Profile",
        illuminance=30,
        temperature=20.0,
        supported_profiles=["GENERIC", "OUTDOOR"],
        profile="OUTDOOR",
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.md2_profile_installation_profile")
    assert state is not None
    assert state.state == "OUTDOOR"
    assert state.attributes.get("device_class") == SensorDeviceClass.ENUM


async def test_motion_detector2_installation_profile_invalid_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """InstallationProfileSensor returns unknown when profile not in supported_profiles."""
    session = mock_setup_dependencies
    device = make_motion_detector2(
        device_id="md2-6",
        name="MD2 Profile Invalid",
        illuminance=30,
        temperature=20.0,
        supported_profiles=["GENERIC", "OUTDOOR"],
        profile="UNKNOWN_FUTURE_VALUE",
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.md2_profile_invalid_installation_profile")
    assert state is not None
    assert state.state == "unknown"


async def test_motion_detector2_communication_quality_diagnostic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """MD2 creates CommunicationQualitySensor when diagnostics enabled."""
    session = mock_setup_dependencies
    device = make_motion_detector2(
        device_id="md2-7",
        name="MD2 Comm",
        illuminance=15,
        temperature=19.5,
        communicationquality=_FakeCommQuality.MEDIUM,
    )
    session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.md2_comm_communication_quality")
    assert state is not None
    assert state.state == "MEDIUM"


# ---------------------------------------------------------------------------
# Shutter Contact 2 — CommunicationQuality (diagnostic only, has attr check)
# ---------------------------------------------------------------------------


async def test_shutter_contact2_communication_quality(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ShutterContact2 with communicationquality attr gets CommunicationQualitySensor."""
    session = mock_setup_dependencies
    device = make_shutter_contact2(
        device_id="sc2-1",
        name="Door Contact",
        communicationquality=_FakeCommQuality.BAD,
    )
    session.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.door_contact_communication_quality")
    assert state is not None
    assert state.state == "BAD"


async def test_shutter_contact2_no_communication_quality_when_attr_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ShutterContact2 WITHOUT communicationquality attr gets no CommunicationQualitySensor."""
    session = mock_setup_dependencies

    # Build a MagicMock WITHOUT communicationquality (use spec to prevent auto-creation)
    device = MagicMock()
    device.id = "sc2-2"
    device.name = "Window Contact"
    device.serial = "sc2-2"
    device.root_device_id = "shc-root"
    device.device_model = "SC2"
    device.manufacturer = "BOSCH"
    device.deleted = False
    device.device_services = []
    device.room_id = "room-1"
    device.supports_batterylevel = False
    device.status = "AVAILABLE"
    # Remove communicationquality so hasattr returns False
    del device.communicationquality

    session.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.window_contact_communication_quality") is None


async def test_shutter_contact2_no_sensors_when_diagnostic_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ShutterContact2 CommunicationQuality not created when diagnostics disabled."""
    config_entry = _make_config_entry_with_options(
        mock_config_entry, {OPT_DIAGNOSTIC_ENTITIES: False}
    )
    session = mock_setup_dependencies
    device = make_shutter_contact2(
        device_id="sc2-3",
        name="Patio Door",
        communicationquality=_FakeCommQuality.GOOD,
    )
    session.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, config_entry)

    assert hass.states.get("sensor.patio_door_communication_quality") is None


# ---------------------------------------------------------------------------
# EmmaPowerSensor — always created from session.emma
# EmmaPowerSensor has _attr_entity_registry_enabled_default = False, so it is
# registered but NOT added to hass.states until enabled via entity_registry.
# ---------------------------------------------------------------------------


async def test_emma_power_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """EmmaPowerSensor is always created from session.emma."""
    session = mock_setup_dependencies
    # Configure the EMMA singleton (already in mock_session as make_device("emma", ...))
    session.emma.value = -500.0  # feeding grid
    session.emma.localizedSubtitles = ["Feeding grid"]
    session.emma.status = "AVAILABLE"
    session.emma.subscribe_callback = MagicMock()
    session.emma.unsubscribe_callback = MagicMock()

    await setup_integration(hass, mock_config_entry)

    # EmmaPowerSensor is disabled by default — enable it via entity registry
    entity_reg = er.async_get(hass)
    entity_entry = entity_reg.async_get("sensor.emma_power")
    assert entity_entry is not None, "sensor.emma_power must be registered"

    entity_reg.async_update_entity("sensor.emma_power", disabled_by=None)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.emma_power")
    assert state is not None
    assert state.state == "-500.0"
    assert state.attributes["unit_of_measurement"] == UnitOfPower.WATT
    assert state.attributes["device_class"] == SensorDeviceClass.POWER
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["power_flow"] == ["Feeding grid"]


# ---------------------------------------------------------------------------
# BatteryLevelSensor — diagnostic, gated by supports_batterylevel
# ---------------------------------------------------------------------------


async def test_battery_level_sensor_thermostat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """BatteryLevelSensor is created when supports_batterylevel is True."""
    session = mock_setup_dependencies
    device = make_thermostat(
        device_id="trv-bat",
        name="Battery TRV",
        temperature=20.0,
        position=40,
        supports_batterylevel=True,
        batterylevel=_FakeBatteryLevel.LOW_BATTERY,
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.battery_trv_battery_level")
    assert state is not None
    assert state.state == "LOW_BATTERY"
    assert state.attributes.get("device_class") == SensorDeviceClass.ENUM


async def test_battery_level_sensor_not_created_when_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """BatteryLevelSensor not created when supports_batterylevel is False."""
    session = mock_setup_dependencies
    device = make_thermostat(
        device_id="trv-nobat",
        name="No Battery TRV",
        supports_batterylevel=False,
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.no_battery_trv_battery_level") is None


async def test_battery_level_sensor_not_created_when_diagnostics_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """BatteryLevelSensor not created when OPT_DIAGNOSTIC_ENTITIES is False."""
    config_entry = _make_config_entry_with_options(
        mock_config_entry, {OPT_DIAGNOSTIC_ENTITIES: False}
    )
    session = mock_setup_dependencies
    device = make_thermostat(
        device_id="trv-batdiag",
        name="Diag Off TRV",
        supports_batterylevel=True,
        batterylevel=_FakeBatteryLevel.OK,
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, config_entry)

    assert hass.states.get("sensor.diag_off_trv_battery_level") is None


async def test_battery_level_sensor_smoke_detector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """BatteryLevelSensor is created for smoke detectors with batterylevel support."""
    session = mock_setup_dependencies
    device = make_device(
        device_id="sd-bat",
        name="Smoke Detector Battery",
        status="AVAILABLE",
        supports_batterylevel=True,
        batterylevel=_FakeBatteryLevel.CRITICAL_LOW,
    )
    session.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.smoke_detector_battery_battery_level")
    assert state is not None
    assert state.state == "CRITICAL_LOW"


async def test_battery_level_sensor_shutter_contact(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """BatteryLevelSensor for shutter contacts with batterylevel support."""
    session = mock_setup_dependencies
    device = make_device(
        device_id="sc-bat",
        name="Front Door Sensor",
        status="AVAILABLE",
        supports_batterylevel=True,
        batterylevel=_FakeBatteryLevel.OK,
    )
    session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.front_door_sensor_battery_level")
    assert state is not None
    assert state.state == "OK"


# ---------------------------------------------------------------------------
# Rating sensors — ValueError fallback to None
# ---------------------------------------------------------------------------


async def test_rating_sensors_return_none_on_value_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Rating sensors return unknown state when rating .name raises ValueError."""
    session = mock_setup_dependencies

    # Use a property that raises ValueError on .name access
    class _BadRating:
        @property
        def name(self):
            raise ValueError("unknown rating")

    bad_rating = _BadRating()

    device = make_twinguard(
        device_id="tg-err",
        name="Twinguard Error",
        temperature=20.0,
        humidity=50.0,
        purity=500,
        combined_rating=bad_rating,
        temperature_rating=bad_rating,
        humidity_rating=bad_rating,
        purity_rating=bad_rating,
        description="",
    )
    session.device_helper.twinguards = [device]

    await setup_integration(hass, mock_config_entry)

    # All rating sensors should degrade to "unknown" not crash
    for entity_id in [
        "sensor.twinguard_error_temperature_rating",
        "sensor.twinguard_error_humidity_rating",
        "sensor.twinguard_error_purity_rating",
        "sensor.twinguard_error_air_quality",
    ]:
        state = hass.states.get(entity_id)
        assert state is not None, f"Missing: {entity_id}"
        assert state.state == "unknown", (
            f"{entity_id} should be unknown, got {state.state}"
        )


# ---------------------------------------------------------------------------
# CommunicationQualitySensor — AttributeError fallback
# ---------------------------------------------------------------------------


async def test_communication_quality_returns_none_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """CommunicationQualitySensor returns unknown when communicationquality.name raises AttributeError."""
    session = mock_setup_dependencies

    class _BadQuality:
        @property
        def name(self):
            raise AttributeError("no name")

    device = make_smart_plug_compact(
        device_id="spc-err",
        name="Error Plug",
        powerconsumption=0.0,
        energyconsumption=0,
        communicationquality=_BadQuality(),
    )
    session.device_helper.smart_plugs_compact = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.error_plug_communication_quality")
    assert state is not None
    assert state.state == "unknown"


# ---------------------------------------------------------------------------
# BatteryLevelSensor — AttributeError fallback
# ---------------------------------------------------------------------------


async def test_battery_level_returns_none_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """BatteryLevelSensor returns unknown when batterylevel.value raises AttributeError."""
    session = mock_setup_dependencies

    class _BadLevel:
        @property
        def value(self):
            raise AttributeError("no value")

    device = make_thermostat(
        device_id="trv-baterr",
        name="Battery Error TRV",
        temperature=20.0,
        position=40,
        supports_batterylevel=True,
        batterylevel=_BadLevel(),
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.battery_error_trv_battery_level")
    assert state is not None
    assert state.state == "unknown"


# ---------------------------------------------------------------------------
# ValveTappetSensor — ValueError on valvestate
# ---------------------------------------------------------------------------


async def test_valve_tappet_extra_attributes_on_value_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ValveTappetSensor extra_state_attributes returns None valve_tappet_state on ValueError."""
    session = mock_setup_dependencies

    class _BadValveState:
        @property
        def name(self):
            raise ValueError("unknown state")

    device = make_thermostat(
        device_id="trv-verr",
        name="Valve Error TRV",
        temperature=22.0,
        position=60,
        valvestate=_BadValveState(),
    )
    session.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.valve_error_trv_valve_tappet")
    assert state is not None
    assert state.state == "60"
    assert state.attributes["valve_tappet_state"] is None


# ---------------------------------------------------------------------------
# Device exclusion by options
# ---------------------------------------------------------------------------


async def test_excluded_device_not_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Devices excluded via OPT_EXCLUDED_DEVICES option are not registered."""
    config_entry = _make_config_entry_with_options(
        mock_config_entry, {OPT_EXCLUDED_DEVICES: ["plug-excl"]}
    )
    session = mock_setup_dependencies
    device = make_smart_plug(
        device_id="plug-excl",
        name="Excluded Plug",
        powerconsumption=100.0,
        energyconsumption=500000,
    )
    session.device_helper.smart_plugs = [device]

    await setup_integration(hass, config_entry)

    assert hass.states.get("sensor.excluded_plug_power") is None
    assert hass.states.get("sensor.excluded_plug_energy") is None


# ---------------------------------------------------------------------------
# Micromodule shutter and blinds — also get Power + Energy sensors
# ---------------------------------------------------------------------------


async def test_micromodule_shutter_power_and_energy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Micromodule shutter control gets Power and Energy sensors."""
    session = mock_setup_dependencies
    device = make_micromodule_shutter_control(
        device_id="msc-1",
        name="Bedroom Shutter",
        powerconsumption=25.0,
        energyconsumption=900000,
    )
    session.device_helper.micromodule_shutter_controls = [device]

    await setup_integration(hass, mock_config_entry)

    power = hass.states.get("sensor.bedroom_shutter_power")
    assert power is not None
    assert power.state == "25.0"

    energy = hass.states.get("sensor.bedroom_shutter_energy")
    assert energy is not None
    assert energy.state == "900.0"


async def test_micromodule_blinds_power_and_energy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Micromodule blinds gets Power and Energy sensors."""
    session = mock_setup_dependencies
    device = make_micromodule_blinds(
        device_id="mb-1",
        name="Office Blinds",
        powerconsumption=10.0,
        energyconsumption=100000,
    )
    session.device_helper.micromodule_blinds = [device]

    await setup_integration(hass, mock_config_entry)

    power = hass.states.get("sensor.office_blinds_power")
    assert power is not None
    assert power.state == "10.0"

    energy = hass.states.get("sensor.office_blinds_energy")
    assert energy is not None
    assert energy.state == "100.0"
