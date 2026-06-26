"""Fixtures for the nexia integration tests."""

from dataclasses import dataclass
from unittest.mock import NonCallableMock, patch

from nexia.automation import NexiaAutomation
from nexia.home import NexiaHome
from nexia.sensor import NexiaSensor
from nexia.thermostat import NexiaThermostat
from nexia.zone import NexiaThermostatZone
import pytest

from homeassistant.components.nexia.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def create_mock_sensor(
    sensor_id: int,
    name: str,
    weight: float = 1.0,
    temperature: float = 72.5,
    humidity: int = 45,
    connected: bool | None = None,
    battery_level: int | None = None,
) -> NonCallableMock[NexiaSensor]:
    """Create a mock NexiaSensor."""
    sensor = NonCallableMock(NexiaSensor)
    sensor.id = sensor_id
    sensor.name = name
    sensor.weight = weight
    sensor.temperature = temperature
    sensor.temperature_valid = True
    sensor.humidity = humidity
    sensor.humidity_valid = True
    sensor.has_online = connected is not None
    sensor.connected = connected
    sensor.has_battery = battery_level is not None
    sensor.battery_level = battery_level
    sensor.battery_valid = battery_level is not None

    return sensor


def create_mock_zone(
    zone_id: int,
    name: str,
    thermostat: NexiaThermostat | None = None,
    *,
    cooling_setpoint: int = 79,
    current_mode: str = "AUTO",
    heating_setpoint: int = 63,
    is_calling: bool = False,
    is_in_permanent_hold: bool = True,
    preset: str = "None",
    presets: list[str] | None = None,
    requested_mode: str = "AUTO",
    sensors: list[NexiaSensor] | None = None,
    setpoint_status: str = "Permanent Hold",
    status: str = "Idle",
    temperature: int = 72,
) -> NonCallableMock[NexiaThermostatZone]:
    """Create a mock NexiaThermostatZone."""
    zone = NonCallableMock(NexiaThermostatZone)
    zone.zone_id = zone_id
    zone.get_name.return_value = name
    zone.thermostat = thermostat
    zone.get_active_sensor_ids.return_value = set()
    zone.get_cooling_setpoint.return_value = cooling_setpoint
    zone.get_current_mode.return_value = current_mode
    zone.get_heating_setpoint.return_value = heating_setpoint
    zone.get_preset.return_value = preset
    zone.get_presets.return_value = presets or ["None", "Home", "Away", "Sleep"]
    zone.get_requested_mode.return_value = requested_mode
    _sensors = sensors or []
    zone.get_sensors.return_value = _sensors
    zone.get_sensor_by_id.side_effect = lambda sid: next(
        s for s in _sensors if s.id == sid
    )
    zone.get_setpoint_status.return_value = setpoint_status
    zone.get_status.return_value = status
    zone.get_temperature.return_value = temperature
    zone.is_calling.return_value = is_calling
    zone.is_in_permanent_hold.return_value = is_in_permanent_hold
    zone.is_native_zone.return_value = True
    zone.load_current_sensor_state.return_value = True
    zone.select_room_iq_sensors.return_value = True
    zone.has_room_iq_monitor.side_effect = lambda: (
        zone.add_room_iq_monitor.call_count > zone.remove_room_iq_monitor.call_count
    )

    return zone


@dataclass
class _ThermostatStateData:
    """Mutable class so thermostat getters and setters can share state."""

    air_cleaner_mode: str
    dehumidify_setpoint: float
    emergency_heat_on: bool
    fan_mode: str
    fan_setpoint: float
    humidify_setpoint: float

    async def async_set_air_cleaner_mode(self, mode: str) -> None:
        """Set the air cleaner mode asynchronously."""
        self.air_cleaner_mode = mode

    async def async_set_dehumidify_setpoint(self, setpoint: float) -> None:
        """Set dehumidify setpoint asynchronously."""
        self.dehumidify_setpoint = setpoint

    async def async_set_emergency_heat_on(self, on: bool) -> None:
        """Set the emergency heat on asynchronously."""
        self.emergency_heat_on = on

    async def async_set_fan_mode(self, mode: str) -> None:
        """Set the fan mode asynchronously."""
        self.fan_mode = mode

    async def async_set_fan_setpoint(self, setpoint: float) -> None:
        """Set the fan setpoint asynchronously."""
        self.fan_setpoint = setpoint

    async def async_set_humidify_setpoint(self, setpoint: float) -> None:
        """Set humidify setpoint asynchronously."""
        self.humidify_setpoint = setpoint


def create_mock_thermostat(
    thermostat_id: int,
    name: str,
    zones: list[NexiaThermostatZone] | None = None,
    *,
    air_cleaner_mode: str = "auto",
    current_compressor_speed: float = 0.0,
    deadband: int = 3,
    dehumidify_setpoint: float = 0.50,
    dehumidify_setpoint_limits: tuple[float, float] = (0.35, 0.65),
    fan_mode: str = "Auto",
    fan_modes: list[str] | None = None,
    fan_speed_setpoint: float = 0.35,
    firmware: str = "5.9.1",
    has_air_cleaner: bool = False,
    has_dehumidify_support: bool = False,
    has_emergency_heat: bool = False,
    has_humidify_support: bool = False,
    has_outdoor_temperature: bool = False,
    has_relative_humidity: bool = False,
    has_variable_fan_speed: bool = False,
    has_variable_speed_compressor: bool = False,
    has_zones: bool = False,
    humidify_setpoint: float = 0.36,
    humidify_setpoint_limits: tuple[float, float] = (0.10, 0.45),
    is_blower_active: bool = False,
    is_emergency_heat_active: bool = False,
    is_online: bool = True,
    model: str = "XL1050",
    outdoor_temperature: float | None = 30.0,
    relative_humidity: float | None = 0.52,
    requested_compressor_speed: float = 0.0,
    setpoint_limits: tuple[int, int] = (55, 99),
    system_status: str = "Idle",
    unit: str = "F",
    variable_fan_speed_limits: tuple[float, float] = (0.35, 1.0),
) -> NonCallableMock[NexiaThermostat]:
    """Create a mock NexiaThermostat."""
    # Mutable class so get_... and set_... share state
    state_data = _ThermostatStateData(
        air_cleaner_mode=air_cleaner_mode,
        dehumidify_setpoint=dehumidify_setpoint,
        emergency_heat_on=is_emergency_heat_active,
        fan_mode=fan_mode,
        fan_setpoint=fan_speed_setpoint,
        humidify_setpoint=humidify_setpoint,
    )

    thermostat = NonCallableMock(NexiaThermostat)
    thermostat.thermostat_id = thermostat_id
    thermostat.zones = zones or []
    thermostat.get_name.return_value = name
    zone_ids = [z.zone_id for z in thermostat.zones]
    thermostat.get_zone_ids.return_value = zone_ids
    thermostat.get_zone_by_id.side_effect = lambda zid: next(
        z for z in thermostat.zones if z.zone_id == zid
    )
    thermostat.get_air_cleaner_mode.side_effect = lambda: state_data.air_cleaner_mode
    thermostat.get_current_compressor_speed.return_value = current_compressor_speed
    thermostat.get_deadband.return_value = deadband
    thermostat.get_dehumidify_setpoint.side_effect = lambda: (
        state_data.dehumidify_setpoint
    )
    thermostat.get_dehumidify_setpoint_limits.return_value = dehumidify_setpoint_limits
    thermostat.get_fan_mode.side_effect = lambda: state_data.fan_mode
    thermostat.get_fan_modes.return_value = fan_modes or ["Auto", "On", "Circulate"]
    thermostat.get_fan_speed_setpoint.side_effect = lambda: state_data.fan_setpoint
    thermostat.get_firmware.return_value = firmware
    thermostat.get_humidify_setpoint.side_effect = lambda: state_data.humidify_setpoint
    thermostat.get_humidify_setpoint_limits.return_value = humidify_setpoint_limits
    thermostat.get_humidity_setpoint_limits.return_value = (
        (humidify_setpoint_limits[0], dehumidify_setpoint_limits[1])
        if has_humidify_support and has_dehumidify_support
        else humidify_setpoint_limits
        if has_humidify_support
        else dehumidify_setpoint_limits
    )
    thermostat.get_model.return_value = model
    thermostat.get_outdoor_temperature.return_value = outdoor_temperature
    thermostat.get_relative_humidity.return_value = relative_humidity
    thermostat.get_requested_compressor_speed.return_value = requested_compressor_speed
    thermostat.get_setpoint_limits.return_value = setpoint_limits
    thermostat.get_system_status.return_value = system_status
    thermostat.get_unit.return_value = unit
    thermostat.get_variable_fan_speed_limits.return_value = variable_fan_speed_limits
    thermostat.has_air_cleaner.return_value = has_air_cleaner
    thermostat.has_dehumidify_support.return_value = has_dehumidify_support
    thermostat.has_emergency_heat.return_value = has_emergency_heat
    thermostat.has_humidify_support.return_value = has_humidify_support
    thermostat.has_outdoor_temperature.return_value = has_outdoor_temperature
    thermostat.has_relative_humidity.return_value = has_relative_humidity
    thermostat.has_variable_fan_speed.return_value = has_variable_fan_speed
    thermostat.has_variable_speed_compressor.return_value = (
        has_variable_speed_compressor
    )
    thermostat.has_zones.return_value = has_zones
    thermostat.is_blower_active.return_value = is_blower_active
    thermostat.is_emergency_heat_active.side_effect = lambda: (
        state_data.emergency_heat_on
    )
    thermostat.is_online = is_online
    thermostat.set_air_cleaner.side_effect = state_data.async_set_air_cleaner_mode
    thermostat.set_dehumidify_setpoint.side_effect = (
        state_data.async_set_dehumidify_setpoint
    )
    thermostat.set_emergency_heat.side_effect = state_data.async_set_emergency_heat_on
    thermostat.set_fan_mode.side_effect = state_data.async_set_fan_mode
    thermostat.set_fan_setpoint.side_effect = state_data.async_set_fan_setpoint
    thermostat.set_humidify_setpoint.side_effect = (
        state_data.async_set_humidify_setpoint
    )

    return thermostat


def create_mock_automation(
    automation_id: int,
    name: str,
    description: str = "",
    enabled: bool = True,
) -> NonCallableMock[NexiaAutomation]:
    """Create a mock NexiaAutomation."""
    automation = NonCallableMock(NexiaAutomation)
    automation.automation_id = automation_id
    automation.name = name
    automation.description = description
    automation.enabled = enabled

    return automation


def create_mock_nexia_home(
    house_id: int = 123456,
    thermostats: list[NexiaThermostat] | None = None,
    automations: list[NexiaAutomation] | None = None,
    root_url: str = "https://www.mynexia.com",
) -> NonCallableMock[NexiaHome]:
    """Create a mock NexiaHome."""
    nexia_home = NonCallableMock(NexiaHome)
    nexia_home.house_id = house_id
    nexia_home.root_url = root_url
    nexia_home.automations_json = [
        {"name": "automation1", "data": 1},
        {"name": "automation2", "data": 2},
    ]
    nexia_home.devices_json = [
        {"name": "device1", "data": 3},
        {"name": "device2", "data": 4},
    ]
    nexia_home.update.return_value = {}

    _thermostats = thermostats or []
    thermostat_ids = [t.thermostat_id for t in _thermostats]
    nexia_home.get_thermostat_ids.return_value = thermostat_ids
    nexia_home.get_thermostat_by_id.side_effect = lambda tid: next(
        t for t in _thermostats if t.thermostat_id == tid
    )
    nexia_home.any_room_iq_monitors.side_effect = lambda: any(
        any(zone.has_room_iq_monitor() for zone in t.zones) for t in _thermostats
    )

    _automations = automations or []
    automation_ids = [a.automation_id for a in _automations]
    nexia_home.get_automation_ids.return_value = automation_ids
    nexia_home.get_automation_by_id.side_effect = lambda aid: next(
        a for a in _automations if a.automation_id == aid
    )

    return nexia_home


@pytest.fixture
def mock_nexia_home() -> NonCallableMock[NexiaHome]:
    """Return a default mock NexiaHome for use in tests that don't need custom setup."""
    zone = create_mock_zone(
        zone_id=100,
        name="Nick Office",
        is_calling=True,
        status="Relieving Air",
        temperature=73,
    )
    thermostat1 = create_mock_thermostat(
        thermostat_id=2000000,
        name="Nick Office",
        zones=[zone],
        has_dehumidify_support=True,
        dehumidify_setpoint=0.45,
        has_relative_humidity=True,
        system_status="Cooling",
    )
    zone.thermostat = thermostat1

    zone = create_mock_zone(zone_id=200, name="Main Zone")
    thermostat2 = create_mock_thermostat(
        thermostat_id=2000001,
        name="Master Suite",
        zones=[zone],
        has_outdoor_temperature=True,
        outdoor_temperature=87.0,  # °F -> ~30.6 °C in the fixture data
        has_relative_humidity=True,
        relative_humidity=0.52,
        has_variable_fan_speed=True,
        fan_speed_setpoint=0.35,
        variable_fan_speed_limits=(0.35, 1.0),
        has_variable_speed_compressor=True,
        current_compressor_speed=0.69,
        requested_compressor_speed=0.69,
        is_blower_active=True,
        system_status="Cooling",
    )
    zone.thermostat = thermostat2

    zone = create_mock_zone(zone_id=300, name="Zone B")
    thermostat3 = create_mock_thermostat(
        thermostat_id=2000002,
        name="Downstairs East Wing",
        zones=[zone],
        has_variable_fan_speed=True,
        fan_speed_setpoint=0.45,
    )
    zone.thermostat = thermostat3

    zone = create_mock_zone(zone_id=400, name="Kitchen", temperature=77)
    thermostat4 = create_mock_thermostat(
        thermostat_id=2000003,
        name="Kitchen",
        zones=[zone],
        has_dehumidify_support=True,
        has_relative_humidity=True,
        relative_humidity=0.36,
    )
    zone.thermostat = thermostat4

    sensor1 = create_mock_sensor(1, "Center", 0.5, temperature=77)
    sensor2 = create_mock_sensor(2, "Upstairs", 0.5, connected=True, battery_level=93)
    sensor3 = create_mock_sensor(3, "Downstairs", 0.0, connected=True)
    sensor3.temperature_valid = False
    zone = create_mock_zone(
        zone_id=500, name="Zone3", sensors=[sensor1, sensor2, sensor3]
    )
    zone.get_active_sensor_ids.return_value = {1, 2}
    thermostat5 = create_mock_thermostat(
        thermostat_id=2000004,
        name="Center NativeZone",
        zones=[zone],
    )
    zone.thermostat = thermostat5

    automations = [
        create_mock_automation(1001, "Away Short", "Sets all zones to away temps."),
        create_mock_automation(1002, "Power Outage", "Hold zones at 55, 90 °F"),
        create_mock_automation(1003, "Power Restored", "Return to Run Schedule"),
    ]

    return create_mock_nexia_home(
        thermostats=[thermostat1, thermostat2, thermostat3, thermostat4, thermostat5],
        automations=automations,
    )


@pytest.fixture
def patch_nexia_home(
    mock_nexia_home: NonCallableMock[NexiaHome],
) -> NonCallableMock[NexiaHome]:
    """Patches NexiaHome to return a mock instance for the duration of a test."""
    with patch(
        "homeassistant.components.nexia.NexiaHome", return_value=mock_nexia_home
    ):
        yield mock_nexia_home


async def setup_integration(
    hass: HomeAssistant, patch_nexia_home: NexiaHome, unique_id: str = "123456"
) -> MockConfigEntry:
    """Set up the nexia integration with a pre-configured mock NexiaHome."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"},
        minor_version=2,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    # validate setup
    for tid in patch_nexia_home.get_thermostat_ids():
        thermostat = patch_nexia_home.get_thermostat_by_id(tid)
        for zid in thermostat.get_zone_ids():
            assert thermostat.get_zone_by_id(zid).thermostat is thermostat

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
