"""Tests for the Habitron sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import Area, SmartController
import pytest

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
    TYPE_DIAG,
    VOLTAGE_DESCRIPTION,
    WIND_DESCRIPTION,
    HbtnDescribedSensor,
    HbtnSensor,
    HbtnSensorEntityDescription,
    LogicSensor,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


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


# ---------------------------------------------------------------------------
# Entity description metadata
# ---------------------------------------------------------------------------


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
    ],
)
def test_static_diagnostic_descriptions(
    description: HbtnSensorEntityDescription,
) -> None:
    """Statically-diagnostic descriptions are hidden by default."""
    assert description.entity_category is EntityCategory.DIAGNOSTIC
    assert description.entity_registry_enabled_default is False


@pytest.mark.parametrize(
    "description",
    [MEMORY_DESCRIPTION, DISK_DESCRIPTION],
)
def test_hub_memory_descriptions_are_user_visible(
    description: HbtnSensorEntityDescription,
) -> None:
    """Memory/Disk free are ordinary, enabled hub sensors."""
    assert description.entity_category is None
    assert description.entity_registry_enabled_default is True


@pytest.mark.parametrize(
    ("description", "expected_icon"),
    [
        (MEMORY_DESCRIPTION, "mdi:memory"),
        (DISK_DESCRIPTION, "mdi:harddisk"),
        (CPU_LOAD_DESCRIPTION, "mdi:timer-alert-outline"),
        (CPU_FREQUENCY_DESCRIPTION, "mdi:clock-fast"),
    ],
)
def test_static_icons_on_descriptions(
    description: HbtnSensorEntityDescription,
    expected_icon: str,
) -> None:
    """Per-purpose static icons live on the description ``icon`` field."""
    assert description.icon == expected_icon


def test_status_description_has_translation_key() -> None:
    """Status uses a translation key; its icon is state-driven via icons.json."""
    assert STATUS_DESCRIPTION.translation_key == "module_status"
    assert STATUS_DESCRIPTION.icon is None


def test_finger_name_description_enum_options() -> None:
    """The finger-name description exposes its stable enum keys."""
    assert EKEY_FINGER_NAME_DESCRIPTION.options is not None
    assert "left_pinky" in EKEY_FINGER_NAME_DESCRIPTION.options
    assert EKEY_FINGER_NAME_DESCRIPTION.state_class is None


# ---------------------------------------------------------------------------
# HbtnDescribedSensor behaviour
# ---------------------------------------------------------------------------


def test_described_sensor_marks_diagnostic_entity_when_flagged() -> None:
    """A sensor whose descriptor type is DIAG is hidden by default."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Iload", type_=TYPE_DIAG)
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


def test_described_sensor_unique_id_appends_key() -> None:
    """The description key keeps otherwise-colliding streams distinct."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Humidity")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    assert entity.unique_id == "Mod_MOD-1_snsr0_humidity"


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
    assert entity._attr_state_class is SensorStateClass.MEASUREMENT


def test_described_text_sensor_has_no_state_class() -> None:
    """Text/enum described sensors carry no state class."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Identifier")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(
        module, sensor_desc, coord, 0, EKEY_USER_NAME_DESCRIPTION
    )
    assert entity._attr_state_class is None
    assert entity._attr_native_value == "None"


def test_finger_name_sensor_sets_options() -> None:
    """The enum finger-name sensor exposes its options on the entity."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor(name="Finger")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(
        module, sensor_desc, coord, 0, EKEY_FINGER_NAME_DESCRIPTION
    )
    assert "left_pinky" in entity.options


def test_hbtnsensor_base_init_and_update() -> None:
    """Base HbtnSensor stores module, unique_id, name and reads from sensors."""
    mod = _make_module()
    mod.sensors[0] = _make_value(23.5)
    desc = _make_sensor_descriptor(name="Temperature", type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnSensor(mod, desc, coord, 5)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "Mod_MOD-1_snsr0"
    assert entity._attr_name == "Temperature"
    assert entity._attr_state_class is SensorStateClass.MEASUREMENT
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 23.5


def test_hbtnsensor_device_info_links_module() -> None:
    """HbtnSensor.device_info points at the module uid."""
    mod = _make_module()
    desc = _make_sensor_descriptor()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnSensor(mod, desc, coord, 0)
    assert ("habitron", "MOD-1") in entity.device_info["identifiers"]


def test_temperature_ext_description_disabled_by_default() -> None:
    """The external temperature probe is disabled by default."""
    assert TEMP_EXT_DESCRIPTION.entity_registry_enabled_default is False
    assert TEMP_DESCRIPTION.entity_registry_enabled_default is True


# ---------------------------------------------------------------------------
# LogicSensor
# ---------------------------------------------------------------------------


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
    assert entity.unique_id == "Mod_MOD-1_logic0"
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
    assert entity.unique_id == "Mod_MOD-1_logic1"
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 7


# ---------------------------------------------------------------------------
# Push subscriptions (subscribe_fn)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("description", "source", "name"),
    [
        (ANALOG_DESCRIPTION, "analogins", "AIn 1"),
        (EKEY_ID_DESCRIPTION, "sensors", "Identifier"),
        (EKEY_FINGER_DESCRIPTION, "sensors", "Finger"),
        (EKEY_USER_NAME_DESCRIPTION, "sensors", "Identifier"),
        (EKEY_FINGER_NAME_DESCRIPTION, "sensors", "Finger"),
        # Hub host-diagnostic sensors also push via subscribe_fn so they stay
        # fresh even though the coordinator uses always_update=False.
        (MEMORY_DESCRIPTION, "sensors", "Memory free"),
        (DISK_DESCRIPTION, "sensors", "Disk free"),
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
        (ANALOG_DESCRIPTION, "analogins", "AIn 1"),
        (EKEY_ID_DESCRIPTION, "sensors", "Identifier"),
        (EKEY_FINGER_DESCRIPTION, "sensors", "Finger"),
    ],
)
async def test_described_sensor_remove_listener(
    description: HbtnSensorEntityDescription,
    source: str,
    name: str,
) -> None:
    """Push descriptions remove the member callback on removal."""
    mod = _make_module()
    getattr(mod, source)[0] = MagicMock()
    sensor_desc = _make_sensor_descriptor(name=name)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(mod, sensor_desc, coord, 0, description)
    await entity.async_will_remove_from_hass()
    getattr(mod, source)[0].remove_listener.assert_called()


async def test_polled_sensor_does_not_subscribe() -> None:
    """A coordinator-polled description (no subscribe_fn) adds no listener."""
    mod = _make_module()
    mod.sensors[0] = MagicMock()
    sensor_desc = _make_sensor_descriptor(name="Humidity")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(mod, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    entity.async_write_ha_state = MagicMock()
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    mod.sensors[0].add_listener.assert_not_called()


async def test_logic_sensor_push_add_and_remove_listener() -> None:
    """LogicSensor registers and removes the logic callback via subscribe_fn."""
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
    mod.logic[0].add_listener.assert_called()
    await entity.async_will_remove_from_hass()
    mod.logic[0].remove_listener.assert_called()


# ---------------------------------------------------------------------------
# eKey value functions (value_fn)
# ---------------------------------------------------------------------------


def _ekey_module() -> MagicMock:
    """Build a stub module exposing one eKey sensor at nmbr 0."""
    mod = MagicMock()
    mod.uid = "EK-1"
    mod.sensors = {0: MagicMock()}
    return mod


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, "None"),
        (255, "Error"),
        (1, "Alice"),  # ids[0]
        (-1, "Alice-disabled"),  # disabled finger → negative id
        (99, "Unknown"),  # out of range
    ],
)
def test_ekey_user_value_fn_translates(raw: int, expected: str) -> None:
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


# ---------------------------------------------------------------------------
# async_setup_entry
# ---------------------------------------------------------------------------


async def test_async_setup_entry_emits_all_sensor_types(hass: HomeAssistant) -> None:
    """async_setup_entry creates the broad mix of sensor entities."""
    # SmartHub-level sensors
    mem = MagicMock()
    mem.name = "Memory free"
    mem.nmbr = 0
    mem.type = 1
    disk = MagicMock()
    disk.name = "Disk free"
    disk.nmbr = 1
    disk.type = 1
    cpu_freq = MagicMock()
    cpu_freq.name = "CPU Frequency"
    cpu_freq.nmbr = 0
    cpu_freq.type = 1
    cpu_load = MagicMock()
    cpu_load.name = "CPU load"
    cpu_load.nmbr = 1
    cpu_load.type = 1
    cpu_temp = MagicMock()
    cpu_temp.name = "CPU Temperature"
    cpu_temp.nmbr = 2
    cpu_temp.type = 1

    # Module-level sensors
    temp = MagicMock()
    temp.name = "Temperature"
    temp.nmbr = 0
    temp.type = 1
    hum = MagicMock()
    hum.name = "Humidity"
    hum.nmbr = 1
    hum.type = 1
    illum = MagicMock()
    illum.name = "Illuminance"
    illum.nmbr = 2
    illum.type = 1
    wind = MagicMock()
    wind.name = "Wind"
    wind.nmbr = 3
    wind.type = 1
    air = MagicMock()
    air.name = "Airquality"
    air.nmbr = 4
    air.type = 1
    ident = MagicMock()
    ident.name = "Identifier"
    ident.nmbr = 5
    ident.type = 1
    finger = MagicMock()
    finger.name = "Finger"
    finger.nmbr = 6
    finger.type = 1
    ain = MagicMock()
    ain.name = "AIn 1"
    ain.nmbr = 0
    ain.type = 3
    ain.area = 0
    logic = MagicMock()
    logic.nmbr = 0
    logic.idx = 0
    logic.name = "Cnt"
    logic.type = 5
    status = MagicMock()
    status.name = "Status"
    status.nmbr = 0
    status.type = 1
    power_temp = MagicMock()
    power_temp.name = "PowerTemp"
    power_temp.nmbr = 1
    power_temp.type = 1

    mod = MagicMock(spec=SmartController)
    mod.uid = "MOD-1"
    mod.mod_type = "Smart Controller Touch"
    mod.typ = b"\x01\x03"
    mod.area = 0
    mod.sensors = [temp, hum, illum, wind, air, ident, finger]
    mod.analogins = [ain]
    mod.logic = [logic]
    mod.diags = [status, power_temp]
    mod.stream_name = "touch_1"

    smhub = MagicMock()
    smhub.sensors = [mem, disk]
    smhub.diags = [cpu_freq, cpu_load, cpu_temp]
    smhub.uid = "HUB-1"

    chan_to = MagicMock()
    chan_to.nmbr = 0
    chan_to.value = 100
    chan_to.type = 1
    chan_curr = MagicMock()
    chan_curr.nmbr = 0
    chan_curr.value = 1.0
    chan_curr.type = 1
    rt_vtg = MagicMock()
    rt_vtg.nmbr = 0
    rt_vtg.value = 230
    rt_vtg.type = 1
    router = MagicMock()
    router.modules = [mod]
    router.coord = MagicMock()
    router.chan_timeouts = [chan_to]
    router.chan_currents = [chan_curr]
    router.voltages = [rt_vtg]
    router.areas = [Area(nmbr=0, name="House")]

    smhub.router = router
    coordinator = MagicMock()
    coordinator.smart_hub = smhub
    entry = MagicMock()
    entry.runtime_data = coordinator

    added: list = []
    await async_setup_entry(hass, entry, added.extend)  # pylint: disable=home-assistant-tests-direct-platform-async-setup-entry

    # 2 hub perc + 3 hub diag + 1 analog + (temp/hum/illum/wind/air) 5
    # + ekey (2 identifier, 2 finger) + 1 logic + 2 module diag
    # + timeout + current + voltage
    assert len(added) == 21
    assert all(isinstance(e, HbtnDescribedSensor) for e in added)
    assert sum(isinstance(e, LogicSensor) for e in added) == 1

    keys = {e.entity_description.key for e in added}
    assert keys == {
        "memory_free",
        "disk_free",
        "cpu_frequency",
        "cpu_load",
        "cpu_temperature",
        "analog",
        "temperature",
        "humidity",
        "illuminance",
        "wind",
        "airquality",
        "ekey_id",
        "ekey_user_name",
        "ekey_finger",
        "ekey_finger_name",
        "logic_state",
        "module_status",
        "power_temp",
        "timeout",
        "current",
        "voltage",
    }
