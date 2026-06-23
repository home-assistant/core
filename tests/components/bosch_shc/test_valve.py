"""Tests for the Bosch SHC valve platform."""

import contextlib
from unittest.mock import MagicMock, PropertyMock

from homeassistant.components.bosch_shc.const import (
    DOMAIN,
    OPT_DIAGNOSTIC_ENTITIES,
    OPT_EXCLUDED_DEVICES,
)
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN, ValveDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_HOST,
    CONF_TOKEN,
    STATE_CLOSED,
    STATE_OPEN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry


def make_thermostat(
    device_id: str = "thermostat-1",
    name: str = "Test Thermostat",
    position: int | None = 50,
) -> MagicMock:
    """Build a mock SHCThermostat that is safe to run through all platforms.

    Sets every attribute that sensor/climate/number/switch/select platform code
    reads during entity-setup to a concrete scalar so HA's JSON state-writer
    never tries to serialize a MagicMock.
    """
    device = make_device(device_id=device_id, name=name, position=position)

    # SHCEntity.available: `device.status == "AVAILABLE"` — must be a string.
    device.status = "AVAILABLE"

    # --- sensor platform ---
    device.temperature = 20.5
    # batterylevel.value must be one of the BatteryLevelSensor._attr_options strings.
    device.batterylevel = MagicMock()
    device.batterylevel.value = "OK"
    device.supports_batterylevel = True
    # valvestate.name is used in ValveTappetSensor.extra_state_attributes.
    device.valvestate = MagicMock()
    device.valvestate.name = "UNKNOWN"

    # --- climate platform ---
    device.setpoint_temperature = 21.0
    device.summer_mode = False
    device.supports_cooling = False
    device.cooling_mode = False
    device.supports_boost_mode = False
    device.boost_mode = False
    device.supports_low = False
    device.low = False
    device.has_demand = False
    device.operation_mode = "AUTOMATIC"
    device.on = False

    # --- number platform (offset) ---
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0

    # --- switch platform ---
    # supports_silentmode: False → no SilentMode switch entity created
    device.supports_silentmode = False
    device.silentmode = False
    # child_lock: compared against enum on_value (SHCThermostat.State.ON).
    # The comparison result is a bool, not a mock, so any concrete value works.
    device.child_lock = False
    device.supports_display_configuration = False
    device.humidity_warning_enabled = None

    # --- select platform ---
    # All supports_display_* guards return False → no extra select entities.
    device.supports_display_direction = False
    device.supports_displayed_temperature = False
    device.supports_wall_thermostat_configuration = False
    device.supports_terminal_configuration = False

    return device


async def test_valve_entity_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A thermostat in device_helper.thermostats creates a valve entity."""
    device = make_thermostat(device_id="thermo-1", name="Living Room Thermostat", position=50)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.living_room_thermostat_valve")
    assert state is not None


async def test_valve_state_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve with position > 0 reports STATE_OPEN."""
    device = make_thermostat(device_id="thermo-open", name="Valve Open", position=75)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.valve_open_valve")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 75


async def test_valve_state_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve with position == 0 reports STATE_CLOSED."""
    device = make_thermostat(device_id="thermo-closed", name="Valve Closed", position=0)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.valve_closed_valve")
    assert state is not None
    assert state.state == STATE_CLOSED
    assert state.attributes["current_position"] == 0


async def test_valve_state_unknown_when_position_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve position returning None results in an unknown state."""
    device = make_thermostat(device_id="thermo-none", name="Valve None", position=None)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.valve_none_valve")
    assert state is not None
    # ValveEntity.state returns None when reports_position=True and position=None;
    # HA renders that as "unknown".
    assert state.state in (None, "unknown", "unavailable")
    assert state.attributes["current_position"] is None


def _make_entry_no_diagnostics() -> MockConfigEntry:
    """Return a config entry with diagnostic entities disabled.

    ValveTappetSensor also reads device.position; disabling diagnostic entities
    prevents it from being created so PropertyMock on .position only affects the
    valve entity under test.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_DIAGNOSTIC_ENTITIES: False},
    )


def _make_thermostat_with_position_error(
    exc: Exception,
    device_id: str,
    name: str,
) -> MagicMock:
    """Return a thermostat mock whose .position raises the given exception.

    Uses a per-call MagicMock subclass so the PropertyMock is not set on the
    shared MagicMock class (which would pollute other tests).

    Instance attributes shadow class-level descriptors in Python, so the
    instance ``position`` attr set by ``make_thermostat`` must be deleted after
    the PropertyMock is installed on the unique subclass.
    """
    # Build a unique subclass per call so the PropertyMock is scoped to it.
    unique_class = type(f"_SHCDevice_{device_id}", (MagicMock,), {})
    device = make_thermostat(device_id=device_id, name=name)
    device.__class__ = unique_class
    unique_class.position = PropertyMock(side_effect=exc)
    # Delete the instance attribute so the class-level PropertyMock takes effect.
    with contextlib.suppress(AttributeError):
        del device.position
    return device


async def test_valve_position_valueerror_returns_none(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A ValueError on .position is caught; current_valve_position returns None."""
    # ValveTappetSensor also reads .position; disable diagnostic entities so it
    # is not created and the PropertyMock only affects the valve entity.
    device = _make_thermostat_with_position_error(
        ValueError("no data"), device_id="thermo-err", name="Valve Error"
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    entry = _make_entry_no_diagnostics()
    await setup_integration(hass, entry)

    state = hass.states.get("valve.valve_error_valve")
    assert state is not None
    assert state.attributes["current_position"] is None
    # State must NOT be open or closed when position is unknown.
    assert state.state not in (STATE_OPEN, STATE_CLOSED)


async def test_valve_position_keyerror_returns_none(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A KeyError on .position is caught; current_valve_position returns None."""
    device = _make_thermostat_with_position_error(
        KeyError("missing"), device_id="thermo-ke", name="Valve KeyError"
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    entry = _make_entry_no_diagnostics()
    await setup_integration(hass, entry)

    state = hass.states.get("valve.valve_keyerror_valve")
    assert state is not None
    assert state.attributes["current_position"] is None


async def test_valve_position_attributeerror_returns_none(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """An AttributeError on .position is caught; current_valve_position returns None."""
    device = _make_thermostat_with_position_error(
        AttributeError("no attr"), device_id="thermo-ae", name="Valve AttributeError"
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    entry = _make_entry_no_diagnostics()
    await setup_integration(hass, entry)

    state = hass.states.get("valve.valve_attributeerror_valve")
    assert state is not None
    assert state.attributes["current_position"] is None


async def test_valve_device_class_water(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve entity has device_class=water."""
    device = make_thermostat(device_id="thermo-dc", name="DC Thermostat", position=30)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.dc_thermostat_valve")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == ValveDeviceClass.WATER


async def test_valve_entity_category_diagnostic(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve entity has entity_category=diagnostic."""
    device = make_thermostat(device_id="thermo-ec", name="EC Thermostat", position=30)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("valve.ec_thermostat_valve")
    assert entry is not None
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_valve_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve unique_id is root_device_id + device_id + 'valve'."""
    device = make_thermostat(device_id="thermo-uid", name="UID Thermostat", position=40)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("valve.uid_thermostat_valve")
    assert entry is not None
    # make_device sets root_device_id="shc-root"; attr_name="Valve" → lower "valve"
    assert entry.unique_id == "shc-root_thermo-uid_valve"


async def test_no_valves_when_thermostats_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """No valve entities are created when the thermostat collection is empty."""
    mock_setup_dependencies.device_helper.thermostats = []

    await setup_integration(hass, mock_config_entry)

    all_valve_states = hass.states.async_all(VALVE_DOMAIN)
    assert len(all_valve_states) == 0


async def test_multiple_thermostats_create_multiple_valves(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Each thermostat produces exactly one valve entity."""
    device_a = make_thermostat(device_id="thermo-a", name="Kitchen Thermostat", position=20)
    device_b = make_thermostat(device_id="thermo-b", name="Bedroom Thermostat", position=0)
    mock_setup_dependencies.device_helper.thermostats = [device_a, device_b]

    await setup_integration(hass, mock_config_entry)

    state_a = hass.states.get("valve.kitchen_thermostat_valve")
    state_b = hass.states.get("valve.bedroom_thermostat_valve")
    assert state_a is not None
    assert state_b is not None
    assert state_a.state == STATE_OPEN
    assert state_b.state == STATE_CLOSED


async def test_excluded_device_not_added(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Thermostat listed in OPT_EXCLUDED_DEVICES is skipped."""
    device = make_thermostat(
        device_id="excluded-thermo", name="Excluded Thermostat", position=30
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_EXCLUDED_DEVICES: ["excluded-thermo"]},
    )
    await setup_integration(hass, config_entry)

    assert hass.states.get("valve.excluded_thermostat_valve") is None


async def test_valve_availability_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve is not unavailable when device status is 'AVAILABLE'."""
    device = make_thermostat(
        device_id="thermo-avail", name="Available Thermostat", position=10
    )
    device.status = "AVAILABLE"
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.available_thermostat_valve")
    assert state is not None
    assert state.state != "unavailable"


async def test_valve_availability_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Valve is unavailable when device status is not 'AVAILABLE'."""
    device = make_thermostat(
        device_id="thermo-unavail", name="Unavailable Thermostat", position=10
    )
    device.status = "OFFLINE"
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.unavailable_thermostat_valve")
    assert state is not None
    assert state.state == "unavailable"


async def test_valve_is_closed_attribute_true(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """is_closed attribute is True when position==0."""
    device = make_thermostat(device_id="thermo-c2", name="Closed Dev", position=0)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.closed_dev_valve")
    assert state is not None
    assert state.attributes.get("is_closed") is True


async def test_valve_is_closed_attribute_false(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """is_closed attribute is False when position > 0."""
    device = make_thermostat(device_id="thermo-o2", name="Open Dev", position=60)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.open_dev_valve")
    assert state is not None
    assert state.attributes.get("is_closed") is False


async def test_valve_reports_position_true(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCValve sets _attr_reports_position=True; state derives from position."""
    # Position 1 → open, Position 0 → closed; no is_opening/is_closing → no
    # OPENING/CLOSING states; confirms reports_position branch is taken.
    device = make_thermostat(device_id="thermo-rp", name="RP Thermostat", position=1)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("valve.rp_thermostat_valve")
    assert state is not None
    # position=1 → OPEN (not CLOSED); reports_position path.
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 1
