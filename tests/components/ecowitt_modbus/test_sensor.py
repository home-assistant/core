"""Test the Ecowitt Modbus sensor platform."""

from ecowitt_modbus import SUPPORTED_MODELS
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecowitt_modbus.const import DOMAIN
from homeassistant.components.ecowitt_modbus.sensor import SENSOR_DESCRIPTIONS
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import ALL_MODELS, WN69LP_CASE, WN90LP_CASE, ModelCase

from tests.common import MockConfigEntry, snapshot_platform

EVERY_MODEL = pytest.mark.parametrize(
    "model_case", ALL_MODELS, ids=lambda case: case.name, indirect=True
)


@EVERY_MODEL
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test every entity each model creates matches its snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@EVERY_MODEL
async def test_each_model_creates_exactly_its_own_entities(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test a model gets its own readings and none of the other's.

    The two models overlap heavily but not completely. Surfacing a WN90LP's
    rain counter on a WN69LP, or a WN69LP's battery voltage on a WN90LP,
    would create an entity that is permanently blank.
    """
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    prefix = f"{model_case.identity(init_integration.entry_id)}_"
    created = {entry.unique_id.removeprefix(prefix) for entry in entries}

    assert created == set(model_case.entity_keys)


@EVERY_MODEL
async def test_the_right_entities_are_disabled_by_default(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test only the duplicated or ambiguous readings are off by default."""
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    prefix = f"{model_case.identity(init_integration.entry_id)}_"
    disabled = {
        entry.unique_id.removeprefix(prefix)
        for entry in entries
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    }

    assert disabled == set(model_case.disabled_keys)


def test_sensor_descriptions_read_real_fields() -> None:
    """Guard SENSOR_DESCRIPTIONS against a component transcription slip.

    Values are resolved by getattr, so a wrong component or reading name
    would otherwise show up as a permanently empty sensor rather than an
    error.
    """
    for case in ALL_MODELS:
        device = case.model(MockModbusConnection().for_unit(case.unit_id))
        for description in SENSOR_DESCRIPTIONS[case.name]:
            component = getattr(device, description.component, None)
            assert component is not None, (
                f"{case.name} has no component {description.component!r}"
            )
            assert hasattr(component, description.key), (
                f"{case.name}'s {description.component} has no "
                f"reading {description.key!r}"
            )


def test_every_supported_model_has_sensor_descriptions() -> None:
    """Test adding a model to the library cannot silently create no entities."""
    assert set(SENSOR_DESCRIPTIONS) == set(SUPPORTED_MODELS)


@pytest.mark.parametrize(
    ("model_case", "key", "expected"),
    [
        (WN90LP_CASE, "light", "17670"),
        (WN90LP_CASE, "uv_index", "1.3"),
        (WN90LP_CASE, "temperature", "26.2"),
        (WN90LP_CASE, "humidity", "60"),
        (WN90LP_CASE, "wind_direction", "150"),
        (WN90LP_CASE, "absolute_pressure", "1001.0"),
        (WN69LP_CASE, "light", "17670"),
        # A whole number here, where the WN90LP reports tenths.
        (WN69LP_CASE, "uv_index", "1"),
        (WN69LP_CASE, "temperature", "26.2"),
        (WN69LP_CASE, "humidity", "60"),
        # The device reports m/s; Home Assistant shows metric wind speeds in
        # km/h, so 1.2 and 2.8 m/s arrive as 4.32 and 10.08.
        (WN69LP_CASE, "wind_speed", "4.32"),
        (WN69LP_CASE, "gust_speed", "10.08"),
        (WN69LP_CASE, "wind_direction", "150"),
        # 139 imperial tips at 0.254mm each.
        (WN69LP_CASE, "rainfall", "35.306"),
        (WN69LP_CASE, "absolute_pressure", "1001.5"),
        (WN69LP_CASE, "battery_voltage", "3.12"),
    ],
    indirect=["model_case"],
    ids=lambda value: value.name if isinstance(value, ModelCase) else str(value),
)
async def test_readings_reach_their_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
    key: str,
    expected: str,
) -> None:
    """Test the specs' worked examples arrive intact as entity states.

    The device library already proves it decodes these registers; this
    proves the integration wires each decoded value to the right entity.
    """
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{model_case.identity(init_integration.entry_id)}_{key}"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@EVERY_MODEL
async def test_an_unavailable_reading_is_reported_as_unknown(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_unit: MockModbusUnit,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test a sensor reporting its invalid sentinel does not read as a number.

    0xFFFF is how these devices say "no reading"; publishing it raw would
    put 6553.5 degrees into the recorder.
    """
    entity_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{model_case.identity(init_integration.entry_id)}_temperature",
    )
    assert entity_id is not None

    mock_unit.holding[model_case.temperature_register] = 0xFFFF
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unknown"


@pytest.mark.parametrize("model_case", [WN69LP_CASE], ids=["WN69LP"], indirect=True)
async def test_the_wn69lps_voltages_are_diagnostic(
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    model_case: ModelCase,
) -> None:
    """Test the power readings are categorised away from the weather ones.

    They describe the sensor's health, not the weather, so they do not
    belong alongside temperature and wind on a dashboard.
    """
    for key in ("battery_voltage", "supply_voltage"):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{model_case.identity(init_integration.entry_id)}_{key}"
        )
        assert entity_id is not None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.entity_category is EntityCategory.DIAGNOSTIC
