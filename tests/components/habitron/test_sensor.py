"""Tests for the Habitron sensor platform."""

from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import (
    Area,
    Diagnostic,
    Input,
    Logic,
    Router,
    Sensor,
    SmartController,
    SmartHub,
)
import pytest

from homeassistant.components.habitron import sensor as habitron_sensor
from homeassistant.components.habitron.const import DOMAIN
from homeassistant.components.habitron.coordinator import HbtnCoordinator
from homeassistant.components.habitron.sensor import (
    AIRQUALITY_DESCRIPTION,
    ANALOG_DESCRIPTION,
    CPU_FREQUENCY_DESCRIPTION,
    CPU_LOAD_DESCRIPTION,
    CPU_TEMPERATURE_DESCRIPTION,
    CURRENT_DESCRIPTION,
    DISK_DESCRIPTION,
    EKEY_FINGER_DESCRIPTION,
    EKEY_FINGER_NAME_DESCRIPTION,
    EKEY_ID_DESCRIPTION,
    EKEY_USER_NAME_DESCRIPTION,
    HUMIDITY_DESCRIPTION,
    ILLUMINANCE_DESCRIPTION,
    MEMORY_DESCRIPTION,
    POWER_TEMP_DESCRIPTION,
    STATUS_DESCRIPTION,
    TEMP_DESCRIPTION,
    TEMP_EXT_DESCRIPTION,
    TIMEOUT_DESCRIPTION,
    VOLTAGE_DESCRIPTION,
    WIND_DESCRIPTION,
    WIND_PEAK_DESCRIPTION,
    HbtnDescribedSensor,
    HbtnHostSensor,
    HbtnSensorEntityDescription,
    LogicSensor,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import MOCK_HOST, MOCK_UID

from tests.common import MockConfigEntry


def _make_module(uid: str = "MOD-1") -> MagicMock:
    """Build a stub module with the dataset attributes the sensor reads."""
    mod = MagicMock()
    mod.uid = uid
    mod.sensors = {}
    mod.chan_currents = {}
    mod.voltages = {}
    mod.chan_timeouts = {}
    mod.diags = {}
    mod.analogins = {}
    mod.logic = {}
    return mod


def _make_sensor_descriptor(name: str = "Humidity", type_: int = 1) -> MagicMock:
    """Build a stub IfDescriptor."""
    desc = MagicMock()
    desc.nmbr = 0
    desc.name = name
    desc.type = type_
    return desc


def _make_value(value: float) -> MagicMock:
    """Build a stub sensor value object."""
    s = MagicMock()
    s.value = value
    return s


def test_humidity_description_attributes() -> None:
    """Humidity description carries device class + unit + value_fn."""
    assert HUMIDITY_DESCRIPTION.device_class is SensorDeviceClass.HUMIDITY
    assert HUMIDITY_DESCRIPTION.native_unit_of_measurement == "%"
    assert HUMIDITY_DESCRIPTION.value_fn is not None
    assert HUMIDITY_DESCRIPTION.diag_check is False


def test_wind_description_carries_translation_key() -> None:
    """Wind description points at the icon-translation key."""
    assert WIND_DESCRIPTION.translation_key == "wind"
    assert WIND_DESCRIPTION.device_class is SensorDeviceClass.WIND_SPEED
    assert WIND_DESCRIPTION.suggested_display_precision == 1


@pytest.mark.parametrize(
    ("description", "expected_dc"),
    [
        (HUMIDITY_DESCRIPTION, SensorDeviceClass.HUMIDITY),
        (ILLUMINANCE_DESCRIPTION, SensorDeviceClass.ILLUMINANCE),
        (WIND_DESCRIPTION, SensorDeviceClass.WIND_SPEED),
        # Air quality is a percentage index, not the standard AQI; no device class.
        (AIRQUALITY_DESCRIPTION, None),
        (CURRENT_DESCRIPTION, SensorDeviceClass.CURRENT),
        (VOLTAGE_DESCRIPTION, SensorDeviceClass.VOLTAGE),
        (TEMP_DESCRIPTION, SensorDeviceClass.TEMPERATURE),
        (POWER_TEMP_DESCRIPTION, SensorDeviceClass.TEMPERATURE),
        (CPU_TEMPERATURE_DESCRIPTION, SensorDeviceClass.TEMPERATURE),
        (CPU_FREQUENCY_DESCRIPTION, SensorDeviceClass.FREQUENCY),
        (EKEY_FINGER_NAME_DESCRIPTION, SensorDeviceClass.ENUM),
    ],
)
def test_descriptions_have_expected_device_class(
    description: HbtnSensorEntityDescription,
    expected_dc: SensorDeviceClass | None,
) -> None:
    """Every description targets the right device class."""
    assert description.device_class is expected_dc


def test_diag_check_flagged_descriptions() -> None:
    """Current/Voltage/Timeout opt into the runtime DIAG fallback."""
    assert CURRENT_DESCRIPTION.diag_check is True
    assert VOLTAGE_DESCRIPTION.diag_check is True
    assert TIMEOUT_DESCRIPTION.diag_check is True
    # Wind/Humidity etc. do not.
    assert WIND_DESCRIPTION.diag_check is False


@pytest.mark.parametrize(
    "description",
    [
        CPU_LOAD_DESCRIPTION,
        CPU_FREQUENCY_DESCRIPTION,
        CPU_TEMPERATURE_DESCRIPTION,
        STATUS_DESCRIPTION,
        POWER_TEMP_DESCRIPTION,
        # Host health of the machine the hub runs on, from the same query as
        # the CPU readings -- not building-automation measurements.
        MEMORY_DESCRIPTION,
        DISK_DESCRIPTION,
    ],
)
def test_static_diagnostic_descriptions(
    description: HbtnSensorEntityDescription,
) -> None:
    """Statically-diagnostic descriptions are hidden by default."""
    assert description.entity_category is EntityCategory.DIAGNOSTIC
    assert description.entity_registry_enabled_default is False


def test_no_description_carries_a_static_icon() -> None:
    """Icons come from ``icons.json``, keyed by translation_key, never from code.

    A static ``icon`` on the description wins over the icon translation and over
    the one a device class implies, so it cannot be themed or translated away.
    """
    for name, value in vars(habitron_sensor).items():
        if isinstance(value, HbtnSensorEntityDescription):
            assert value.icon is None, f"{name} carries a static icon"


def test_every_icon_translation_key_exists() -> None:
    """Each icons.json sensor key belongs to a description that asks for it."""
    icons = json.loads(
        (Path(habitron_sensor.__file__).parent / "icons.json").read_text(
            encoding="utf-8"
        )
    )
    described = {
        value.translation_key
        for value in vars(habitron_sensor).values()
        if isinstance(value, HbtnSensorEntityDescription)
    }
    assert set(icons["entity"]["sensor"]) <= described


def test_status_description_has_translation_key() -> None:
    """Status uses a translation key; its icon is state-driven via icons.json."""
    assert STATUS_DESCRIPTION.translation_key == "module_status"
    assert STATUS_DESCRIPTION.icon is None


def test_finger_name_description_enum_options() -> None:
    """The finger-name description exposes its stable enum keys."""
    assert EKEY_FINGER_NAME_DESCRIPTION.options is not None
    assert "left_pinky" in EKEY_FINGER_NAME_DESCRIPTION.options
    assert EKEY_FINGER_NAME_DESCRIPTION.state_class is None


@pytest.mark.parametrize(
    "description",
    [STATUS_DESCRIPTION, EKEY_ID_DESCRIPTION, EKEY_FINGER_DESCRIPTION],
)
def test_categorical_descriptions_have_no_state_class(
    description: HbtnSensorEntityDescription,
) -> None:
    """Categorical/identifier sensors carry no MEASUREMENT state class."""
    assert description.state_class is None


def test_described_sensor_marks_diagnostic_entity_when_flagged() -> None:
    """A sensor whose descriptor type is DIAG is hidden by default."""
    module = _make_module()
    # 10 is the bus role code the library reports as ``is_diagnostic``.
    sensor_desc = _make_sensor_descriptor(name="Iload", type_=10)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, CURRENT_DESCRIPTION)
    assert entity.entity_description is CURRENT_DESCRIPTION
    assert entity._attr_entity_registry_enabled_default is False


def test_described_sensor_not_diagnostic_for_normal_type() -> None:
    """A non-DIAG type stays user-visible."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    assert getattr(entity, "_attr_entity_registry_enabled_default", True) is not False


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        # One member of its kind per device: the key alone identifies it.
        (HUMIDITY_DESCRIPTION, "MOD-1_humidity"),
        (ILLUMINANCE_DESCRIPTION, "MOD-1_illuminance"),
        (WIND_DESCRIPTION, "MOD-1_wind"),
        (WIND_PEAK_DESCRIPTION, "MOD-1_wind_peak"),
        (AIRQUALITY_DESCRIPTION, "MOD-1_airquality"),
        (TEMP_DESCRIPTION, "MOD-1_temperature"),
        (TEMP_EXT_DESCRIPTION, "MOD-1_temperature_external"),
        (EKEY_ID_DESCRIPTION, "MOD-1_ekey_identifier"),
        (EKEY_USER_NAME_DESCRIPTION, "MOD-1_ekey_user_name"),
        # Several per device, so the member number tells them apart.
        (CURRENT_DESCRIPTION, "MOD-1_current_0"),
        (VOLTAGE_DESCRIPTION, "MOD-1_voltage_0"),
        (TIMEOUT_DESCRIPTION, "MOD-1_timeout_0"),
        (ANALOG_DESCRIPTION, "MOD-1_analog_in_0"),
    ],
)
def test_described_sensor_unique_id(
    description: HbtnSensorEntityDescription, expected: str
) -> None:
    """Only descriptions that would collide carry the key suffix."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Humidity")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, description)
    assert entity.unique_id == expected


def test_only_multi_member_descriptions_are_numbered() -> None:
    """Pin which descriptions append the member number.

    Forgetting it where a device carries several members of that kind gives
    them one id and silently drops all but one; adding it where there is only
    one changes that entity's id for no reason. Both belong in a test rather
    than in someone's memory.
    """
    numbered = {
        name
        for name, obj in vars(habitron_sensor).items()
        if isinstance(obj, HbtnSensorEntityDescription) and obj.numbered
    }
    assert numbered == {
        "CURRENT_DESCRIPTION",
        "VOLTAGE_DESCRIPTION",
        "TIMEOUT_DESCRIPTION",
        "ANALOG_DESCRIPTION",
    }


def test_described_sensor_keeps_bus_name_when_not_translated() -> None:
    """Non-translated descriptions display the bus member name."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Humidity")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    assert entity._attr_name == "Humidity"


def test_described_sensor_drops_bus_name_when_translated() -> None:
    """Translated descriptions delete the bus name so translation_key wins."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Identifier")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, EKEY_ID_DESCRIPTION)
    assert not hasattr(entity, "_attr_name")
    assert entity.entity_description.translation_key == "ekey_id"


@pytest.mark.parametrize(
    ("description", "source", "expected"),
    [
        (HUMIDITY_DESCRIPTION, "sensors", 42.0),
        (CURRENT_DESCRIPTION, "chan_currents", 1.25),
        (VOLTAGE_DESCRIPTION, "voltages", 231.5),
        (TIMEOUT_DESCRIPTION, "chan_timeouts", 7),
        (TEMP_DESCRIPTION, "sensors", 21.5),
        (STATUS_DESCRIPTION, "diags", 0),
        (POWER_TEMP_DESCRIPTION, "diags", 55.0),
        (CPU_LOAD_DESCRIPTION, "diags", 12.0),
    ],
)
def test_described_sensor_value_fn_source(
    description: HbtnSensorEntityDescription,
    source: str,
    expected: float,
) -> None:
    """value_fn reads from the module attribute bound in the description."""
    module = _make_module()
    getattr(module, source)[0] = _make_value(expected)
    sensor_desc = _make_sensor_descriptor(type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, description)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == expected


def test_described_sensor_inherits_measurement_state_class() -> None:
    """Numeric described sensors are MEASUREMENT state-class."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    # The public property, not the private attribute: SensorEntity reads the
    # state class off the description itself, so nothing copies it over.
    assert entity.state_class is SensorStateClass.MEASUREMENT


def test_described_text_sensor_has_no_state_class() -> None:
    """Text/enum described sensors carry no state class."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Identifier")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(
        module, sensor_desc, coord, 0, EKEY_USER_NAME_DESCRIPTION
    )
    assert entity.state_class is None
    # No seeded value: the entity stays unknown until the bus reports a user.
    assert entity._attr_native_value is None


def test_finger_name_sensor_sets_options() -> None:
    """The enum finger-name sensor exposes its options on the entity."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Finger")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(
        module, sensor_desc, coord, 0, EKEY_FINGER_NAME_DESCRIPTION
    )
    assert "left_pinky" in entity.options


def test_shared_base_names_the_member_and_links_the_device() -> None:
    """What the shared base contributes: the member's name and the device link.

    Exercised through a described sensor, the only shape the platform builds.
    The base carries no unique_id and is never instantiated on its own, so
    testing it directly would pin behaviour nothing ships.
    """
    mod = _make_module()
    desc = _make_sensor_descriptor(name="Temperature", type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(mod, desc, coord, 5, HUMIDITY_DESCRIPTION)
    assert entity._attr_name == "Temperature"
    assert ("habitron", "MOD-1") in entity.device_info["identifiers"]


def test_temperature_ext_description_disabled_by_default() -> None:
    """The external temperature probe is disabled by default."""
    assert TEMP_EXT_DESCRIPTION.entity_registry_enabled_default is False
    assert TEMP_DESCRIPTION.entity_registry_enabled_default is True


def test_logic_sensor_unique_id_name_and_update() -> None:
    """LogicSensor reads from module.logic[idx] and templates its name."""
    mod = _make_module()
    mod.logic = {0: _make_value(42)}
    logic = MagicMock()
    logic.nmbr = 0
    logic.idx = 0
    logic.name = "Counter"
    logic.type = 5
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = LogicSensor(mod, logic, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "MOD-1_logic_0"
    assert not hasattr(entity, "_attr_name")
    assert entity._attr_translation_placeholders == {"number": "1", "name": "Counter"}
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 42


def test_logic_sensor_value_uses_idx_not_nmbr() -> None:
    """The logic value/subscription index is logic.idx, not logic.nmbr."""
    mod = _make_module()
    mod.logic = {3: _make_value(7)}
    logic = MagicMock()
    logic.nmbr = 1
    logic.idx = 3
    logic.name = "Runtime"
    logic.type = 5
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = LogicSensor(mod, logic, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "MOD-1_logic_1"
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 7


@pytest.mark.parametrize(
    ("description", "source", "name"),
    [
        # Router telemetry pushes via subscribe_fn: the library refreshes it on
        # every poll independently of the compact-status CRC, so a coordinator
        # that only fires on a CRC change would otherwise leave these stale.
        (CURRENT_DESCRIPTION, "chan_currents", "Current 1"),
        (VOLTAGE_DESCRIPTION, "voltages", "Voltage 1"),
        (TIMEOUT_DESCRIPTION, "chan_timeouts", "Timeout 1"),
        # Hub host-diagnostic sensors also push via subscribe_fn so they stay
        # fresh even though the coordinator uses always_update=False.
        (MEMORY_DESCRIPTION, "sensors", "Memory usage"),
        (DISK_DESCRIPTION, "sensors", "Disk usage"),
        (CPU_LOAD_DESCRIPTION, "diags", "CPU load"),
        (CPU_FREQUENCY_DESCRIPTION, "diags", "CPU Frequency"),
        (CPU_TEMPERATURE_DESCRIPTION, "diags", "CPU Temperature"),
    ],
)
async def test_described_sensor_add_listener(
    description: HbtnSensorEntityDescription,
    source: str,
    name: str,
) -> None:
    """Push descriptions register the member callback on add."""
    mod = _make_module()
    getattr(mod, source)[0] = MagicMock()
    sensor_desc = _make_sensor_descriptor(name=name)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(mod, sensor_desc, coord, 0, description)
    entity.async_write_ha_state = MagicMock()
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    getattr(mod, source)[0].add_listener.assert_called()


@pytest.mark.parametrize(
    ("description", "source", "name"),
    [
        # The members that genuinely need a subscription: they change
        # independently of the module CRC, so the coordinator alone would
        # leave them stale.
        (CURRENT_DESCRIPTION, "chan_currents", "Current 1"),
        (CPU_LOAD_DESCRIPTION, "diags", "CPU load"),
    ],
)
async def test_described_sensor_remove_listener(
    description: HbtnSensorEntityDescription,
    source: str,
    name: str,
) -> None:
    """Push descriptions unsubscribe through the on-remove callbacks.

    Registered there rather than in ``async_will_remove_from_hass``, because
    that hook is skipped when adding the entity fails after it subscribed --
    ``entity_platform`` aborts by running only the on-remove callbacks.
    """
    mod = _make_module()
    member = MagicMock()
    getattr(mod, source)[0] = member
    sensor_desc = _make_sensor_descriptor(name=name)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(mod, sensor_desc, coord, 0, description)
    entity.async_write_ha_state = MagicMock()

    await _run_added_to_hass(entity)
    member.add_listener.assert_called_once()

    # What ``add_to_platform_abort`` and ``async_remove`` both run.
    entity._call_on_remove_callbacks()
    member.remove_listener.assert_called_once_with(entity._handle_coordinator_update)


@pytest.mark.parametrize(
    ("description", "source", "name"),
    [
        (HUMIDITY_DESCRIPTION, "sensors", "Humidity"),
        # Analogue values live in the compact status mirror and reach the
        # entity through the coordinator; subscribing would write twice.
        (ANALOG_DESCRIPTION, "analogins", "AIn 1"),
    ],
)
async def test_polled_sensor_does_not_subscribe(
    description: HbtnSensorEntityDescription,
    source: str,
    name: str,
) -> None:
    """A coordinator-polled description (no subscribe_fn) adds no listener."""
    mod = _make_module()
    getattr(mod, source)[0] = MagicMock()
    sensor_desc = _make_sensor_descriptor(name=name)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(mod, sensor_desc, coord, 0, description)
    entity.async_write_ha_state = MagicMock()
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    getattr(mod, source)[0].add_listener.assert_not_called()


async def test_logic_sensor_does_not_subscribe() -> None:
    """LogicSensor leaves the update to the coordinator, without subscribing.

    Counter values come from the compact status mirror, which the module CRC
    covers, so the coordinator already fans out on a change; a subscription
    would write the state a second time.
    """
    mod = _make_module()
    mod.logic = {0: MagicMock()}
    logic = MagicMock()
    logic.nmbr = 0
    logic.idx = 0
    logic.name = "Counter"
    logic.type = 5
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = LogicSensor(mod, logic, coord, 0)
    entity.async_write_ha_state = MagicMock()
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    mod.logic[0].add_listener.assert_not_called()


def _ekey_module() -> MagicMock:
    """Build a stub module exposing one eKey sensor at nmbr 0."""
    mod = MagicMock()
    mod.uid = "EK-1"
    mod.sensors = {0: MagicMock()}
    return mod


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, None),  # no current user -> unknown, like the finger sensor
        (255, "Error"),
        (1, "Alice"),  # ids[0]
        (-1, "Alice-disabled"),  # disabled finger → negative id
        (99, "Unknown"),  # out of range
    ],
)
def test_ekey_user_value_fn_translates(raw: int, expected: str | None) -> None:
    """The user-name value_fn maps the raw identifier to a user string."""
    mod = _ekey_module()
    user = MagicMock()
    user.name = "Alice"
    mod.ids = [user]
    mod.sensors[0].value = raw
    assert EKEY_USER_NAME_DESCRIPTION.value_fn(mod, 0) == expected


@pytest.mark.parametrize("raw", [0, 255, 99])
def test_ekey_finger_value_fn_special_values(raw: int) -> None:
    """Idle (0), error (255) and out-of-range map to no state (None)."""
    mod = _ekey_module()
    mod.sensors[0].value = raw
    assert EKEY_FINGER_NAME_DESCRIPTION.value_fn(mod, 0) is None


def test_ekey_finger_value_fn_named_finger() -> None:
    """A finger value in 1..10 resolves to a stable enum key (not display text)."""
    mod = _ekey_module()
    mod.sensors[0].value = 1
    result = EKEY_FINGER_NAME_DESCRIPTION.value_fn(mod, 0)
    assert result == "left_pinky"
    assert result in EKEY_FINGER_NAME_DESCRIPTION.options


async def test_setup_registers_the_broad_mix_of_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_with_model: Callable[..., Awaitable[MockConfigEntry]],
) -> None:
    """A full bus yields one registered entity per member the platform serves.

    Counted in the entity registry rather than in the list the platform hands
    back: that is what Home Assistant ends up with, diagnostics included -- they
    are registered but disabled, so they never appear as a state.
    """
    hub = SmartHub(uid=MOCK_UID)
    hub.sensors = [
        Sensor(name="Memory usage", nmbr=0, type=1),
        Sensor(name="Disk usage", nmbr=1, type=1),
    ]
    hub.diags = [
        Diagnostic(name="CPU Frequency", nmbr=0, type=1),
        Diagnostic(name="CPU load", nmbr=1, type=1),
        Diagnostic(name="CPU Temperature", nmbr=2, type=1),
    ]

    module = SmartController(
        uid="MOD-1", addr=1, typ=b"\x01\x03", name="Controller", area=1
    )
    module.sensors = [
        Sensor(name="Temperature", nmbr=0, type=1),
        Sensor(name="Humidity", nmbr=1, type=1),
        Sensor(name="Illuminance", nmbr=2, type=1),
        Sensor(name="Wind", nmbr=3, type=1),
        Sensor(name="Airquality", nmbr=4, type=1),
        Sensor(name="Identifier", nmbr=5, type=1),
        Sensor(name="Finger", nmbr=6, type=1),
    ]
    module.analogins = [Input(name="AIn 1", nmbr=0, type=3, area=0)]
    module.logic = [Logic(name="Counter 1", nmbr=1, idx=0, type=5)]
    module.diags = [
        Diagnostic(name="Status", nmbr=0, type=1),
        Diagnostic(name="PowerTemp", nmbr=1, type=1),
    ]

    router = Router(uid="rt_1", name="Router")
    router.modules = [module]
    router.areas = [Area(nmbr=1, name="Living")]
    router.chan_timeouts = [Diagnostic(name="Timeouts channel 1", nmbr=0, type=1)]
    router.chan_currents = [Diagnostic(name="Current channel 1", nmbr=0, type=1)]
    router.voltages = [Diagnostic(name="Voltage 5V", nmbr=0, type=1)]

    entry = await setup_with_model(router, hub)

    registered = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    # 2 hub perc + 3 hub diag + 1 analog + (temp/hum/illum/wind/air) 5
    # + ekey (2 identifier, 2 finger) + 1 logic + 2 module diag
    # + timeout + current + voltage
    assert len(registered) == 21
    assert all(item.domain == "sensor" for item in registered)


_ANALOG_UNIQUE_ID = "MOD-1_analog_in_0"


@pytest.fixture
def setup_with_model(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
) -> Callable[[Router, SmartHub | None], Awaitable[MockConfigEntry]]:
    """Set up the entry the way Home Assistant does, over a given bus model.

    Only the bus itself is replaced: the config entry is set up through
    ``hass.config_entries.async_setup``, so the platform is forwarded, the
    entities are registered and the registries end up in the state the tests
    assert on -- rather than the tests inspecting the objects the platform
    happened to construct.
    """

    async def _setup(router: Router, hub: SmartHub | None = None) -> MockConfigEntry:
        async def _connect_and_build(coordinator: HbtnCoordinator) -> None:
            coordinator._client = AsyncMock()
            coordinator.host = MOCK_HOST
            coordinator.hub = hub if hub is not None else SmartHub(uid=MOCK_UID)
            coordinator.base_url = f"http://{MOCK_HOST}:7780"
            coordinator.router = router

        # A test that pre-registers entities adds the entry itself first.
        if hass.config_entries.async_get_entry(mock_config_entry.entry_id) is None:
            mock_config_entry.add_to_hass(hass)
        with (
            patch(
                "homeassistant.components.habitron.coordinator."
                "HbtnCoordinator._async_connect_and_build",
                new=_connect_and_build,
            ),
            patch(
                "homeassistant.components.habitron.coordinator.async_refresh_system",
                new=AsyncMock(return_value=4711),
            ),
            patch(
                "homeassistant.components.habitron.coordinator.async_refresh_hub",
                new=AsyncMock(),
            ),
        ):
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()
        return mock_config_entry

    return _setup


def _analog_router(ain_area: int, module_area: int = 1) -> Router:
    """A bus with one controller carrying a single analog input."""
    module = SmartController(
        uid="MOD-1",
        addr=1,
        typ=b"\x01\x03",
        name="Controller",
        area=module_area,
    )
    module.analogins = [Input(name="AIn 1", nmbr=0, type=3, area=ain_area)]
    router = Router(uid="rt_1", name="Router")
    router.modules = [module]
    router.areas = [Area(nmbr=1, name="Living"), Area(nmbr=2, name="Kitchen")]
    return router


def _analog_entity_with_area(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_id: str,
) -> HbtnDescribedSensor:
    """Build a registered analog sensor carrying a deviating ``area_id``.

    ``async_add_entities`` registers asynchronously, so the deviating area is
    applied from the entity's own ``async_added_to_hass`` (after registration),
    not at platform-setup time -- which is what these tests drive directly.
    """
    mod = _make_module()
    mod.analogins[0] = _make_value(1.0)
    sensor_desc = _make_sensor_descriptor(name="AIn 1", type_=3)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(
        mod, sensor_desc, coord, 0, ANALOG_DESCRIPTION, initial_area_id=area_id
    )
    reg_entry = entity_registry.async_get_or_create("sensor", DOMAIN, entity.unique_id)
    entity.hass = hass
    entity.entity_id = reg_entry.entity_id
    entity.registry_entry = reg_entry
    entity.async_write_ha_state = MagicMock()
    return entity


async def _run_added_to_hass(entity: HbtnDescribedSensor) -> None:
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()


async def test_analog_deviating_area_applied_when_unset(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """An analog input with no area of its own adopts its deviating area."""
    kitchen = area_registry.async_get_or_create("Kitchen")
    entity = _analog_entity_with_area(hass, entity_registry, kitchen.id)

    await _run_added_to_hass(entity)

    assert entity_registry.async_get(entity.entity_id).area_id == kitchen.id


async def test_analog_deviating_area_stamped_only_on_first_create(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    setup_with_model: Callable[..., Awaitable[MockConfigEntry]],
) -> None:
    """A brand-new analog input carries its deviating area into the entity."""
    entry = await setup_with_model(_analog_router(ain_area=2, module_area=1))

    kitchen = area_registry.async_get_area_by_name("Kitchen")
    assert kitchen is not None
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, _ANALOG_UNIQUE_ID)
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).area_id == kitchen.id
    assert entry.state is ConfigEntryState.LOADED


async def test_analog_deviating_area_not_restamped_on_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    setup_with_model: Callable[..., Awaitable[MockConfigEntry]],
) -> None:
    """On reload the deviating area is not re-applied.

    ``area_id is None`` after a reload can mean the user cleared the entity's
    area to inherit the device area; re-stamping the deviating area would
    silently overwrite that choice, so an already-registered entity carries no
    ``initial_area_id``.
    """
    mock_config_entry.add_to_hass(hass)
    # Registered as if from a prior run, with the area the user has since cleared.
    entity_registry.async_get_or_create(
        "sensor", DOMAIN, _ANALOG_UNIQUE_ID, config_entry=mock_config_entry
    )

    await setup_with_model(_analog_router(ain_area=2, module_area=1))

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, _ANALOG_UNIQUE_ID)
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).area_id is None


async def test_bus_areas_are_not_created_up_front(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    setup_with_model: Callable[..., Awaitable[MockConfigEntry]],
) -> None:
    """A reload does not resurrect bus areas the user has since removed.

    ``async_get_or_create`` matches by name, so creating every bus area on each
    setup would recreate one the user renamed or deleted. Only the area an
    entity is actually being stamped with may be created.
    """
    # The analog input matches its module's area, so no area has to be stamped.
    await setup_with_model(_analog_router(ain_area=1, module_area=1))

    assert area_registry.async_get_area_by_name("Living") is None
    assert area_registry.async_get_area_by_name("Kitchen") is None


@pytest.mark.parametrize("ain_area", [0, 1])
async def test_analog_non_deviating_area_not_applied(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ain_area: int,
    setup_with_model: Callable[..., Awaitable[MockConfigEntry]],
) -> None:
    """No area override for an analog input that matches its module's area."""
    await setup_with_model(_analog_router(ain_area=ain_area, module_area=1))

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, _ANALOG_UNIQUE_ID)
    assert entity_id is not None
    assert entity_registry.async_get(entity_id).area_id is None


async def test_analog_input_created_for_module_type_beyond_hardcoded_set(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_with_model: Callable[..., Awaitable[MockConfigEntry]],
) -> None:
    """Any module the library gave analog inputs gets its analog sensors.

    The platform iterates the ``analogins`` the library populated instead of an
    enumerated set of type codes, so a controller variant beyond the ones that
    used to be hard-coded still yields its analog input.
    """
    router = _analog_router(ain_area=0)
    router.modules[0].typ = b"\x01\x05"

    await setup_with_model(router)

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, _ANALOG_UNIQUE_ID)
        is not None
    )


@pytest.mark.parametrize(
    ("readings_ok", "expected"),
    [pytest.param(True, True, id="fresh"), pytest.param(False, False, id="stale")],
)
def test_host_sensor_unavailable_while_the_hub_stays_silent(
    readings_ok: bool, expected: bool
) -> None:
    """A hub reading reports itself unavailable once its poll stops answering.

    The host poll swallows its errors so a hiccup cannot take the bus entities
    down with it; the cost is that the last CPU/memory/disk value would stand
    forever, looking live. Only these entities follow the host poll -- a bus
    sensor built from the same class is untouched by it.
    """
    coord = MagicMock(spec=DataUpdateCoordinator)
    coord.host_readings_ok = readings_ok
    coord.last_update_success = True
    hub = SmartHub(diags=[Diagnostic(name="CPU load", nmbr=0, type=10, value=42.0)])

    host_entity = HbtnHostSensor(hub, hub.diags[0], coord, 0, CPU_LOAD_DESCRIPTION)
    assert host_entity.available is expected

    bus_entity = HbtnDescribedSensor(
        _make_module(), _make_sensor_descriptor(type_=1), coord, 0, HUMIDITY_DESCRIPTION
    )
    assert bus_entity.available is True


async def test_host_readings_unknown_until_first_hub_answer() -> None:
    """Host readings stay unknown until the host query has actually answered.

    ``Diagnostic``/``Sensor`` default to 0, which reads as a genuine measurement
    (0 % CPU load, 0 % disk usage) rather than as a missing value, so the
    entities must report ``None`` until the first successful read.
    """
    hub = SmartHub(
        diags=[Diagnostic(name="CPU load", nmbr=0, type=10, value=42.0)],
        sensors=[Sensor(name="Memory usage", nmbr=0, type=2, value=17.0)],
    )
    # A freshly built hub has not been polled yet.
    assert hub.host_valid is False
    for description in (
        CPU_FREQUENCY_DESCRIPTION,
        CPU_LOAD_DESCRIPTION,
        CPU_TEMPERATURE_DESCRIPTION,
        MEMORY_DESCRIPTION,
        DISK_DESCRIPTION,
    ):
        assert description.value_fn(hub, 0) is None

    hub.host_valid = True
    assert CPU_LOAD_DESCRIPTION.value_fn(hub, 0) == 42.0
    assert MEMORY_DESCRIPTION.value_fn(hub, 0) == 17.0
