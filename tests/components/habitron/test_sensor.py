"""Tests for the Habitron sensor platform."""

from unittest.mock import MagicMock

from habitron_client import Area
import pytest

from homeassistant.components.habitron.sensor import (
    AIRQUALITY_DESCRIPTION,
    CURRENT_DESCRIPTION,
    HUMIDITY_DESCRIPTION,
    ILLUMINANCE_DESCRIPTION,
    TIMEOUT_DESCRIPTION,
    TYPE_DIAG,
    VOLTAGE_DESCRIPTION,
    WIND_DESCRIPTION,
    EKeyFingerNameSensor,
    EKeyUserNameSensor,
    HbtnDescribedSensor,
    HbtnSensorEntityDescription,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
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
    ],
)
def test_descriptions_have_expected_device_class(
    description: HbtnSensorEntityDescription,
    expected_dc: SensorDeviceClass | None,
) -> None:
    """Every description targets the right device class."""
    assert description.device_class is expected_dc


def test_diag_check_flagged_descriptions() -> None:
    """Current/Voltage/Timeout opt into the DIAG fallback."""
    assert CURRENT_DESCRIPTION.diag_check is True
    assert VOLTAGE_DESCRIPTION.diag_check is True
    assert TIMEOUT_DESCRIPTION.diag_check is True
    # Wind/Humidity etc. do not.
    assert WIND_DESCRIPTION.diag_check is False


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
    # ``_attr_entity_registry_enabled_default`` is the SensorEntity
    # default (True / unset) for normal entities.
    assert getattr(entity, "_attr_entity_registry_enabled_default", True) is not False


def test_described_sensor_value_fn_humidity() -> None:
    """value_fn reads from ``module.sensors`` for Humidity."""
    module = _make_module()
    module.sensors[0] = _make_value(42.0)
    sensor_desc = _make_sensor_descriptor()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 42.0


def test_described_sensor_value_fn_current_from_chan_currents() -> None:
    """value_fn for Current reads from ``module.chan_currents``."""
    module = _make_module()
    module.chan_currents[0] = _make_value(1.25)
    sensor_desc = _make_sensor_descriptor(type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, CURRENT_DESCRIPTION)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 1.25


def test_described_sensor_value_fn_voltage_from_voltages() -> None:
    """value_fn for Voltage reads from ``module.voltages``."""
    module = _make_module()
    module.voltages[0] = _make_value(231.5)
    sensor_desc = _make_sensor_descriptor(type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, VOLTAGE_DESCRIPTION)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 231.5


def test_described_sensor_value_fn_timeout_from_chan_timeouts() -> None:
    """value_fn for Timeout reads from ``module.chan_timeouts``."""
    module = _make_module()
    module.chan_timeouts[0] = _make_value(7)
    sensor_desc = _make_sensor_descriptor(type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, TIMEOUT_DESCRIPTION)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 7


def test_described_sensor_inherits_measurement_state_class() -> None:
    """All described sensors are MEASUREMENT state-class (inherited from base)."""
    module = _make_module()
    sensor_desc = _make_sensor_descriptor()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDescribedSensor(module, sensor_desc, coord, 0, HUMIDITY_DESCRIPTION)
    # State class comes from HbtnSensor base.
    assert entity._attr_state_class is SensorStateClass.MEASUREMENT


# Note: the full-integration setup smoke test lives in test_init once every
# platform is migrated (it loads all platforms via ``setup_integration``).


# ---------- Additional tests for non-described sensor classes ----------


from homeassistant.components.habitron.sensor import (  # noqa: E402
    AnalogSensor,
    EKeySensorFngr,
    EKeySensorId,
    FrequencySensor,
    HbtnDiagSensor,
    HbtnSensor,
    LogicSensor,
    PercSensor,
    StatusSensor,
    TemperatureDSensor,
    TemperatureSensor,
)


def _make_hbtnsensor_module() -> MagicMock:
    """Build a fuller stub module with all sensor source lists populated."""
    mod = _make_module()
    mod.sensors[0] = _make_value(23.5)
    mod.analogins[0] = _make_value(75)
    mod.logic = {0: _make_value(42)}
    mod.diags = {0: _make_value(99.9)}
    return mod


def test_hbtnsensor_base_init_and_update() -> None:
    """Base HbtnSensor stores module, unique_id, name and reads from sensors."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Temperature", type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnSensor(mod, desc, coord, 5)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "Mod_MOD-1_snsr0"
    assert entity.name == "Temperature"
    assert entity._attr_state_class is SensorStateClass.MEASUREMENT
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 23.5


def test_temperature_sensor_disables_temperature_ext() -> None:
    """A ``Temperature ext.`` sensor is disabled by default."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Temperature ext.")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = TemperatureSensor(mod, desc, coord, 0)
    assert entity._attr_entity_registry_enabled_default is False
    assert entity._attr_device_class is SensorDeviceClass.TEMPERATURE


def test_temperature_sensor_normal_stays_enabled() -> None:
    """A regular temperature sensor stays enabled by default."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Temperature")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = TemperatureSensor(mod, desc, coord, 0)
    assert getattr(entity, "_attr_entity_registry_enabled_default", True) is not False


def test_analog_sensor_unique_id_and_value() -> None:
    """AnalogSensor uses an adin-prefixed unique id and reads analogins."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Analog 1")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = AnalogSensor(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "Mod_MOD-1_adin0"
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 75


def test_ekey_sensor_id_unique_id_and_passthrough() -> None:
    """EKeySensorId is a simple sensor exposing the raw identifier value."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Identifier")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = EKeySensorId(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "Mod_MOD-1_ekey_ident"
    assert entity._attr_name == "Identifier Value"
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 23.5


def test_ekey_sensor_fngr_unique_id_and_passthrough() -> None:
    """EKeySensorFngr exposes the raw finger value via the base updater."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Finger")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = EKeySensorFngr(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "Mod_MOD-1_ekey_fngr"
    assert entity._attr_name == "Finger Value"
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 23.5


def test_hbtn_diag_sensor_disabled_by_default() -> None:
    """HbtnDiagSensor entities are diagnostic and disabled by default."""
    mod = _make_hbtnsensor_module()
    diag = _make_sensor_descriptor(name="CPU")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDiagSensor(mod, diag, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity._attr_entity_registry_enabled_default is False
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 99.9


def test_temperature_d_sensor_attributes() -> None:
    """TemperatureDSensor is a Celsius diagnostic temperature."""
    mod = _make_hbtnsensor_module()
    diag = _make_sensor_descriptor(name="PowerTemp")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = TemperatureDSensor(mod, diag, coord, 0)
    assert entity._attr_device_class is SensorDeviceClass.TEMPERATURE
    assert entity.unique_id == "Mod_MOD-1_PowerTemp"


def test_status_sensor_icon_flips_on_value() -> None:
    """StatusSensor toggles its icon based on the value."""
    mod = _make_hbtnsensor_module()
    diag = _make_sensor_descriptor(name="Status")
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = StatusSensor(mod, diag, coord, 0)
    entity.async_write_ha_state = MagicMock()
    # value > 0 → disconnect icon
    mod.diags[0].value = 1
    entity._handle_coordinator_update()
    assert entity._attr_icon == "mdi:lan-disconnect"
    # value 0 → check icon
    mod.diags[0].value = 0
    entity._handle_coordinator_update()
    assert entity._attr_icon == "mdi:lan-check"


def test_logic_sensor_unique_id_and_update() -> None:
    """LogicSensor reads from module.logic and unique-ids itself."""
    mod = _make_hbtnsensor_module()
    logic_desc = MagicMock()
    logic_desc.nmbr = 0
    logic_desc.idx = 0
    logic_desc.name = "Counter"
    logic_desc.type = 5
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = LogicSensor(mod, logic_desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity.unique_id == "Mod_MOD-1_logic0"
    assert entity._attr_name == "Cnt1: Counter"
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 42


@pytest.mark.parametrize(
    ("name", "expected_icon"),
    [
        ("memory usage", "mdi:memory"),
        ("disk usage", "mdi:harddisk"),
        ("cpu load", "mdi:timer-alert-outline"),
        ("some other", "mdi:percent-circle-outline"),
    ],
)
def test_perc_sensor_icon_by_name(name: str, expected_icon: str) -> None:
    """PercSensor picks an icon based on its name prefix."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name=name, type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = PercSensor(mod, desc, coord, 0)
    assert entity._attr_icon == expected_icon


def test_perc_sensor_diag_branch() -> None:
    """A diagnostic PercSensor reads from diags rather than sensors."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="cpu load", type_=TYPE_DIAG)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = PercSensor(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    assert entity._attr_entity_category is not None
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 99.9


@pytest.mark.parametrize(
    ("name", "expected_icon"),
    [
        ("cpu frequency", "mdi:clock-fast"),
        ("zigbee", "mdi:sine-wave"),
    ],
)
def test_frequency_sensor_icon_by_name(name: str, expected_icon: str) -> None:
    """FrequencySensor picks an icon based on its name."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name=name, type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = FrequencySensor(mod, desc, coord, 0)
    assert entity._attr_icon == expected_icon
    assert entity._attr_device_class is SensorDeviceClass.FREQUENCY


def test_frequency_sensor_diag_branch() -> None:
    """A diagnostic FrequencySensor reads from diags rather than sensors."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="cpu frequency", type_=TYPE_DIAG)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = FrequencySensor(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 99.9


# ---------- Tests covering async_added/async_will_remove + setup_entry ----------

from unittest.mock import AsyncMock, patch  # noqa: E402

from habitron_client import SmartController  # noqa: E402

from homeassistant.components.habitron.sensor import (  # noqa: E402
    LogicSensorPush,
    async_setup_entry,
)


def test_hbtnsensor_device_info_links_module() -> None:
    """HbtnSensor.device_info points at the module uid."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnSensor(mod, desc, coord, 0)
    assert ("habitron", "MOD-1") in entity.device_info["identifiers"]


def test_hbtn_diag_sensor_device_info_links_module() -> None:
    """HbtnDiagSensor.device_info points at the module uid."""
    mod = _make_hbtnsensor_module()
    diag = _make_sensor_descriptor()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = HbtnDiagSensor(mod, diag, coord, 0)
    assert ("habitron", "MOD-1") in entity.device_info["identifiers"]


async def test_analog_sensor_add_listener() -> None:
    """AnalogSensor.async_added_to_hass registers the input callback."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor()
    desc.add_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = AnalogSensor(mod, desc, coord, 0)
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    desc.add_listener.assert_called()


async def test_analog_sensor_remove_listener() -> None:
    """AnalogSensor.async_will_remove_from_hass removes the callback."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor()
    desc.remove_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = AnalogSensor(mod, desc, coord, 0)
    await entity.async_will_remove_from_hass()
    desc.remove_listener.assert_called()


async def test_ekey_id_sensor_add_listener() -> None:
    """EKeySensorId registers the descriptor callback."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Identifier")
    desc.add_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = EKeySensorId(mod, desc, coord, 0)
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    desc.add_listener.assert_called()


async def test_ekey_id_sensor_remove_listener() -> None:
    """EKeySensorId removes its descriptor callback."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Identifier")
    desc.remove_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = EKeySensorId(mod, desc, coord, 0)
    await entity.async_will_remove_from_hass()
    desc.remove_listener.assert_called()


async def test_ekey_fngr_sensor_add_listener() -> None:
    """EKeySensorFngr registers the descriptor callback."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Finger")
    desc.add_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = EKeySensorFngr(mod, desc, coord, 0)
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    desc.add_listener.assert_called()


async def test_ekey_fngr_sensor_remove_listener() -> None:
    """EKeySensorFngr removes its descriptor callback."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="Finger")
    desc.remove_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = EKeySensorFngr(mod, desc, coord, 0)
    await entity.async_will_remove_from_hass()
    desc.remove_listener.assert_called()


async def test_logic_sensor_push_add_listener() -> None:
    """LogicSensorPush registers the logic callback."""
    mod = _make_hbtnsensor_module()
    logic = MagicMock()
    logic.nmbr = 0
    logic.idx = 0
    logic.name = "Counter"
    logic.type = 5
    logic.add_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = LogicSensorPush(mod, logic, coord, 0)
    with patch(
        "homeassistant.helpers.update_coordinator."
        "CoordinatorEntity.async_added_to_hass",
        new=AsyncMock(),
    ):
        await entity.async_added_to_hass()
    logic.add_listener.assert_called()


async def test_logic_sensor_push_remove_listener() -> None:
    """LogicSensorPush removes the logic callback on remove."""
    mod = _make_hbtnsensor_module()
    logic = MagicMock()
    logic.nmbr = 0
    logic.idx = 0
    logic.name = "Counter"
    logic.type = 5
    logic.remove_listener = MagicMock()
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = LogicSensorPush(mod, logic, coord, 0)
    await entity.async_will_remove_from_hass()
    logic.remove_listener.assert_called()


def test_perc_sensor_normal_branch_reads_sensors() -> None:
    """PercSensor for a non-DIAG type reads from module.sensors."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="memory free", type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = PercSensor(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 23.5


def test_frequency_sensor_normal_branch_reads_sensors() -> None:
    """FrequencySensor for a non-DIAG type reads from module.sensors."""
    mod = _make_hbtnsensor_module()
    desc = _make_sensor_descriptor(name="cpu frequency", type_=1)
    coord = MagicMock(spec=DataUpdateCoordinator)
    entity = FrequencySensor(mod, desc, coord, 0)
    entity.async_write_ha_state = MagicMock()
    entity._handle_coordinator_update()
    assert entity._attr_native_value == 23.5


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

    entry = MagicMock()
    entry.runtime_data = smhub
    entry.runtime_data.router = router

    added: list = []
    with patch("homeassistant.components.habitron.sensor.er.async_get") as mock_get:
        registry = MagicMock()
        registry.async_get_entity_id = MagicMock(return_value="sensor.fake")
        mock_get.return_value = registry
        await async_setup_entry(hass, entry, added.extend)  # pylint: disable=home-assistant-tests-direct-platform-async-setup-entry

    assert any(isinstance(e, PercSensor) for e in added)
    assert any(isinstance(e, TemperatureDSensor) for e in added)
    assert any(isinstance(e, FrequencySensor) for e in added)
    assert any(isinstance(e, AnalogSensor) for e in added)
    assert any(isinstance(e, TemperatureSensor) for e in added)
    assert any(isinstance(e, HbtnDescribedSensor) for e in added)
    assert any(isinstance(e, EKeySensorId) for e in added)
    assert any(isinstance(e, EKeySensorFngr) for e in added)
    assert any(isinstance(e, LogicSensorPush) for e in added)
    assert any(isinstance(e, StatusSensor) for e in added)


async def test_async_setup_entry_analog_area_assignment_external(
    hass: HomeAssistant,
) -> None:
    """An analog input with a non-default area gets the area_id assigned."""
    ain = MagicMock()
    ain.name = "AIn 1"
    ain.nmbr = 0
    ain.type = 3
    ain.area = 5
    mod = MagicMock()
    mod.uid = "MOD-A"
    mod.mod_type = "Other"
    mod.typ = b"\x01\x03"
    mod.area = 0
    mod.sensors = []
    mod.analogins = [ain]
    mod.logic = []
    mod.diags = []

    smhub = MagicMock()
    smhub.sensors = []
    smhub.diags = []
    smhub.uid = "HUB-1"
    router = MagicMock()
    router.modules = [mod]
    router.coord = MagicMock()
    router.chan_timeouts = []
    router.chan_currents = []
    router.voltages = []
    router.areas = [Area(nmbr=5, name="area_5_id")]

    entry = MagicMock()
    entry.runtime_data = smhub
    entry.runtime_data.router = router

    with patch("homeassistant.components.habitron.sensor.er.async_get") as mock_get:
        registry = MagicMock()
        registry.async_get_entity_id = MagicMock(return_value="sensor.fake")
        mock_get.return_value = registry
        await async_setup_entry(hass, entry, lambda es: None)  # pylint: disable=home-assistant-tests-direct-platform-async-setup-entry

    registry.async_update_entity.assert_called_with("sensor.fake", area_id="area_5_id")


async def test_async_setup_entry_analog_area_overflow_falls_back(
    hass: HomeAssistant,
) -> None:
    """An out-of-range analog area is clamped to the default."""
    ain = MagicMock()
    ain.name = "AIn 1"
    ain.nmbr = 0
    ain.type = 3
    ain.area = 99
    mod = MagicMock()
    mod.uid = "MOD-OV"
    mod.mod_type = "Other"
    mod.typ = b"\x01\x03"
    mod.area = 0
    mod.sensors = []
    mod.analogins = [ain]
    mod.logic = []
    mod.diags = []

    smhub = MagicMock()
    smhub.sensors = []
    smhub.diags = []
    smhub.uid = "HUB-1"
    router = MagicMock()
    router.modules = [mod]
    router.coord = MagicMock()
    router.chan_timeouts = []
    router.chan_currents = []
    router.voltages = []
    router.areas = [Area(nmbr=0, name="House")]

    entry = MagicMock()
    entry.runtime_data = smhub
    entry.runtime_data.router = router

    with patch("homeassistant.components.habitron.sensor.er.async_get") as mock_get:
        registry = MagicMock()
        registry.async_get_entity_id = MagicMock(return_value="sensor.fake")
        mock_get.return_value = registry
        await async_setup_entry(hass, entry, lambda es: None)  # pylint: disable=home-assistant-tests-direct-platform-async-setup-entry

    registry.async_update_entity.assert_called_with("sensor.fake", area_id=None)


# ---------------------------------------------------------------------------
# eKey name-translating sensors
# ---------------------------------------------------------------------------


def _ekey_module() -> MagicMock:
    """Build a stub module exposing one eKey identifier sensor at nmbr 0."""
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
def test_ekey_user_name_sensor_translates(raw: int, expected: str) -> None:
    """The user-name sensor maps the raw identifier to a user string."""
    coord = MagicMock(spec=DataUpdateCoordinator)
    mod = _ekey_module()
    user = MagicMock()
    user.name = "Alice"
    mod.ids = [user]
    entity = EKeyUserNameSensor(mod, 0, coord, 0)
    entity.async_write_ha_state = MagicMock()

    mod.sensors[0].value = raw
    entity._handle_coordinator_update()
    assert entity._attr_native_value == expected


@pytest.mark.parametrize("raw", [0, 255, 99])
def test_ekey_finger_name_sensor_special_values(raw: int) -> None:
    """Idle (0), error (255) and out-of-range map to no state (None)."""
    coord = MagicMock(spec=DataUpdateCoordinator)
    mod = _ekey_module()
    entity = EKeyFingerNameSensor(mod, 0, coord, 0)
    entity.async_write_ha_state = MagicMock()

    mod.sensors[0].value = raw
    entity._handle_coordinator_update()
    assert entity._attr_native_value is None


def test_ekey_finger_name_sensor_named_finger() -> None:
    """A finger value in 1..10 resolves to a stable enum key (not display text)."""
    coord = MagicMock(spec=DataUpdateCoordinator)
    mod = _ekey_module()
    entity = EKeyFingerNameSensor(mod, 0, coord, 0)
    entity.async_write_ha_state = MagicMock()

    mod.sensors[0].value = 1
    entity._handle_coordinator_update()
    assert entity._attr_native_value == "left_pinky"
    assert entity._attr_native_value in entity.options
