"""Tests for lazy entity creation on the aioabrp telemetry driver."""

from typing import Any
from unittest.mock import AsyncMock

from aioabrp import Telemetry
import pytest

from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    SENSOR_TEST_SUB,
    build_metric_value,
)

from tests.common import MockConfigEntry

SOC_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_soc"
POWER_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_power"
VOLTAGE_ENTITY_ID = "sensor.rivian_r2_2027_standard_long_range_voltage"

VOLTAGE_ENTITY_ID_2 = "sensor.rivian_r1s_2024_quad_max_voltage"


async def _lazy_setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration with the synchronous ``fake_stream`` double."""
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# Not in the mocked garage, so the stream never subscribes to it.
_ABSENT_VEHICLE_ID = 999999999999


def _unique_id_lookup(
    entity_registry: er.EntityRegistry, vehicle_id: int, key: str
) -> str | None:
    """Look up an entity_id via ``unique_id`` to decouple from strings.json slugs."""
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{SENSOR_TEST_SUB}_{vehicle_id}_{key}"
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_stream_only_metric_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """The seed is empty; a power frame arrives over the stream."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(1234.0)))
    await hass.async_block_till_done()

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "1234.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_post_setup_frame_creates_entity(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """The seed is empty; voltage arrives only after setup completes."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0))
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is not None
    state = hass.states.get(VOLTAGE_ENTITY_ID)
    assert state is not None
    assert state.state == "400.0"

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    # Pin via the registry: ``state.attributes`` never carries the category.
    registry_entry = entity_registry.async_get(VOLTAGE_ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_lazy_create_idempotent_on_repeated_frames(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Two consecutive non-null power frames must create exactly one power entity."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(POWER_ENTITY_ID) is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(5000.0)))
    await hass.async_block_till_done()

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(power=build_metric_value(6000.0)))
    await hass.async_block_till_done()

    all_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry_with_vehicles.entry_id
    )
    power_entries = [e for e in all_entries if e.entity_id == POWER_ENTITY_ID]
    assert len(power_entries) == 1

    state = hass.states.get(POWER_ENTITY_ID)
    assert state is not None
    assert state.state == "6000.0"


@pytest.mark.usefixtures("mock_abrp_client")
@pytest.mark.parametrize(
    ("active_vehicle_id", "expected_entity_id", "absent_entity_id"),
    [
        pytest.param(
            MOCK_VEHICLE_ID,
            VOLTAGE_ENTITY_ID,
            VOLTAGE_ENTITY_ID_2,
            id="vehicle_a_active",
        ),
        pytest.param(
            MOCK_VEHICLE_ID_2,
            VOLTAGE_ENTITY_ID_2,
            VOLTAGE_ENTITY_ID,
            id="vehicle_b_active",
        ),
    ],
)
async def test_multi_vehicle_entity_isolation(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
    active_vehicle_id: int,
    expected_entity_id: str,
    absent_entity_id: str,
) -> None:
    """Voltage arriving for vehicle A must not create a voltage entity for vehicle B."""
    entry = config_entry_with_vehicles

    await _lazy_setup(hass, entry)

    assert entity_registry.async_get(absent_entity_id) is None

    fake_stream.fire_frame(
        active_vehicle_id, Telemetry(voltage=build_metric_value(400.0))
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(expected_entity_id) is not None
    assert entity_registry.async_get(absent_entity_id) is None


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
async def test_absent_metric_entities_not_created(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
) -> None:
    """An empty seed with no stream frames must produce zero telemetry entities."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert entity_registry.async_get(SOC_ENTITY_ID) is None
    assert entity_registry.async_get(POWER_ENTITY_ID) is None
    assert entity_registry.async_get(VOLTAGE_ENTITY_ID) is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soe_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """An ``soe`` frame lazy-creates the SoE sensor; native Wh, display kWh."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe") is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soe=build_metric_value(75000.0)))
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soe")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "75.0"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy_storage"
    assert state.attributes["state_class"] == "measurement"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_odometer_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """An ``odometer`` frame lazy-creates the odometer sensor; native m, display km."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "odometer") is None

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(odometer=build_metric_value(123456.0))
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "odometer")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "123.456"
    assert float(state.state) == pytest.approx(123.456)
    assert state.attributes["unit_of_measurement"] == "km"
    assert state.attributes["device_class"] == "distance"
    assert state.attributes["state_class"] == "total_increasing"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_calibrated_ref_cons_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A ``calibrated_ref_cons`` frame lazy-creates the ref-consumption sensor."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons")
        is None
    )

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(calibrated_ref_cons=build_metric_value(175.0))
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(
        entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(175.0)
    assert state.attributes["unit_of_measurement"] == "Wh/km"
    assert state.attributes["device_class"] == "energy_distance"
    assert state.attributes["state_class"] == "measurement"

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_capacity_sensor_lazy_creates_static(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A ``battery_capacity`` frame lazy-creates the capacity sensor as STATIC."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity") is None
    )

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_capacity=build_metric_value(75000.0))
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "75.0"
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == "energy_storage"
    assert "state_class" not in state.attributes, (
        "battery_capacity is STATIC; state_class must be absent (LTS opt-out)"
    )

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soh_sensor_lazy_creates_on_first_frame(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A ``soh`` frame lazy-creates the State-of-Health sensor (percent)."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh") is None

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soh=build_metric_value(92.0)))
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "92.0"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["state_class"] == "measurement"
    assert "device_class" not in state.attributes, (
        "SoH is not SensorDeviceClass.BATTERY (that's SoC); device_class must be absent"
    )

    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_temperature_sensor_stays_primary_category(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """Battery Temperature stays primary (``entity_category is None``)."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_temperature")
        is None
    )

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_temperature=build_metric_value(22.5))
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(
        entity_registry, MOCK_VEHICLE_ID, "battery_temperature"
    )
    assert entity_id is not None
    registry_entry = entity_registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.entity_category is None, (
        "battery_temperature is the canonical preconditioning trigger; "
        "it must stay primary (no entity_category)"
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_soh_above_100_percent_surfaces_uncapped(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A post-recalibration SoH overshoot (> 100%) surfaces uncapped."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(MOCK_VEHICLE_ID, Telemetry(soh=build_metric_value(105.0)))
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "soh")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(105.0)


@pytest.mark.usefixtures("mock_abrp_client")
async def test_battery_capacity_recalibration_jump_updates_state(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A capacity recalibration jump is reflected in ``state.state``."""

    await _lazy_setup(hass, config_entry_with_vehicles)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_capacity=build_metric_value(75000.0))
    )
    await hass.async_block_till_done()

    entity_id = _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "battery_capacity")
    assert entity_id is not None
    first_state = hass.states.get(entity_id)
    assert first_state is not None
    assert first_state.state == "75.0"

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(battery_capacity=build_metric_value(74500.0))
    )
    await hass.async_block_till_done()

    second_state = hass.states.get(entity_id)
    assert second_state is not None
    assert second_state.state == "74.5"


@pytest.mark.usefixtures("mock_abrp_client")
async def test_new_sensor_multi_vehicle_isolation(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_abrp_client: AsyncMock,
    fake_stream: Any,
) -> None:
    """A metric frame for vehicle A must not create the entity on vehicle B."""
    entry = config_entry_with_vehicles

    await _lazy_setup(hass, entry)

    fake_stream.fire_frame(
        MOCK_VEHICLE_ID, Telemetry(calibrated_ref_cons=build_metric_value(175.0))
    )
    await hass.async_block_till_done()

    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID, "calibrated_ref_cons")
        is not None
    )
    assert (
        _unique_id_lookup(entity_registry, MOCK_VEHICLE_ID_2, "calibrated_ref_cons")
        is None
    )

    # A frame for an id outside the garage must not mint an entity either.
    fake_stream.fire_frame(_ABSENT_VEHICLE_ID, Telemetry(soc=build_metric_value(50.0)))
    await hass.async_block_till_done()

    assert _unique_id_lookup(entity_registry, _ABSENT_VEHICLE_ID, "soc") is None
