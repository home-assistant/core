"""Test EcoNet sensors."""

from collections.abc import Awaitable, Callable

from pyeconet.equipment import Equipment
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.econet.const import DOMAIN
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, Platform, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.parametrize("platform", [Platform.SENSOR])


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "equipment_data", ["water_heater", "thermostat"], indirect=True
)
async def test_sensors(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Sensors have translated names, stable unique IDs, and expected states."""
    await setup_integration()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_running_updates(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_equipment: Equipment,
) -> None:
    """The translated running-state sensor still receives updates."""
    await setup_integration()
    mock_equipment.update_equipment_info(
        {"device_name": "device_1", "@RUNNING": "Running"}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.gas_water_heater_running_state").state == "Running"


async def test_enabled_defaults(
    setup_integration: Callable[[], Awaitable[None]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Naming changes keep Wi-Fi disabled by default and other sensors enabled."""
    await setup_integration()
    assert {
        entry.entity_id: entry.disabled_by
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entry.disabled_by is not None
    } == {"sensor.gas_water_heater_wi_fi_signal": er.RegistryEntryDisabler.INTEGRATION}


async def test_existing_registry_choices_preserved(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep custom names and IDs while adopting HA's device-relative display."""
    existing = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "device_1_Gas Water Heater_compressor_health",
        suggested_object_id="gas_water_heater_gas_water_heater_compressor_health",
        has_entity_name=False,
    )
    entity_registry.async_update_entity(
        existing.entity_id,
        name="My health sensor",
    )
    await setup_integration()

    updated = entity_registry.async_get(existing.entity_id)
    assert updated.id == existing.id
    assert updated.unique_id == existing.unique_id
    assert updated.name == "My health sensor"
    assert updated.compat_name is None
    assert hass.states.get(existing.entity_id).name == (
        "Gas Water Heater My health sensor"
    )


async def test_existing_id_can_be_regenerated(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep a legacy ID until the user explicitly regenerates it."""
    old_id = "sensor.gas_water_heater_gas_water_heater_override_status"
    new_id = "sensor.gas_water_heater_override_status"
    existing = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "device_1_Gas Water Heater_override_status",
        suggested_object_id=old_id.removeprefix("sensor."),
        original_name="Gas Water Heater_override_status",
        object_id_base="Gas Water Heater_override_status",
        has_entity_name=False,
    )
    await setup_integration()

    updated = entity_registry.async_get(old_id)
    assert updated.id == existing.id
    assert updated.unique_id == existing.unique_id
    assert updated.original_name == "Override status"
    assert entity_registry.async_get(new_id) is None
    assert entity_registry.async_regenerate_entity_id(updated) == new_id

    entity_registry.async_update_entity(old_id, new_entity_id=new_id)
    await hass.async_block_till_done()
    assert entity_registry.async_get(old_id) is None
    assert entity_registry.async_get(new_id).id == existing.id
    assert entity_registry.async_get(new_id).unique_id == existing.unique_id


@pytest.mark.usefixtures("energy_usage")
@pytest.mark.parametrize(
    ("energy_usage", "expected"),
    [
        pytest.param("KBTU", "2.93", id="gas"),
        pytest.param("KWH", "10", id="electric"),
    ],
    indirect=["energy_usage"],
)
async def test_energy_conversion(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    expected: str,
) -> None:
    """The renamed energy sensor still converts the library's usage into kWh."""
    await setup_integration()
    state = hass.states.get("sensor.gas_water_heater_energy_usage_today")
    assert state.state == expected
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR
