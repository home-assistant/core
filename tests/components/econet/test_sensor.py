"""Test EcoNet sensors."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from pyeconet.equipment import Equipment
from pyeconet.errors import InvalidResponseFormat
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.econet.const import DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    Platform,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

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


@pytest.mark.usefixtures("energy_usage")
@pytest.mark.parametrize(
    ("energy_usage", "energy_entities"),
    [
        pytest.param(("KBTU", None), {}, id="missing"),
        pytest.param(
            ("KBTU", 0), {"sensor.gas_water_heater_energy_usage_today": None}, id="zero"
        ),
        pytest.param(
            ("KBTU", 10),
            {"sensor.gas_water_heater_energy_usage_today": None},
            id="reported",
        ),
    ],
    indirect=["energy_usage"],
)
async def test_enabled_defaults(
    setup_integration: Callable[[], Awaitable[None]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    energy_entities: dict[str, er.RegistryEntryDisabler | None],
) -> None:
    """Create only sensors with values while retaining zero and empty states."""
    await setup_integration()
    assert {
        entry.entity_id: entry.disabled_by
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == {
        **energy_entities,
        "sensor.gas_water_heater_alert_count": None,
        "sensor.gas_water_heater_wi_fi_signal": er.RegistryEntryDisabler.INTEGRATION,
        "sensor.gas_water_heater_running_state": None,
    }


async def test_existing_registry_choices_preserved(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    equipment_data: dict,
) -> None:
    """Keep custom names and IDs while adopting HA's device-relative display."""
    equipment_data["@COMBUSTION"] = {"value": 0}
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
    assert updated.disabled_by is None
    assert updated.compat_name is None
    assert hass.states.get(existing.entity_id).name == (
        "Gas Water Heater My health sensor"
    )


async def test_existing_id_can_be_regenerated(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    entity_registry: er.EntityRegistry,
    equipment_data: dict,
) -> None:
    """Keep a legacy ID until the user explicitly regenerates it."""
    equipment_data["@OVERRIDESTATUS"] = ""
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


@pytest.mark.usefixtures("energy_usage", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("energy_usage", "expected"),
    [
        pytest.param(("KBTU", 10), "2.93", id="gas"),
        pytest.param(("KWH", 10), "10", id="electric"),
        pytest.param(("KBTU", 0), "0.0", id="gas_zero"),
        pytest.param(("KWH", 0), "0", id="electric_zero"),
    ],
    indirect=["energy_usage"],
)
async def test_energy_conversion(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    expected: str,
) -> None:
    """Convert energy usage into kWh while preserving zero values."""
    await setup_integration()
    state = hass.states.get("sensor.gas_water_heater_energy_usage_today")
    assert state.state == expected
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("field", "value", "missing_value", "entity_id", "expected"),
    [
        pytest.param(
            "@TANK",
            {"value": 0},
            {"value": None},
            "sensor.gas_water_heater_tank_health",
            "0",
            id="zero",
        ),
        pytest.param(
            "@OVERRIDESTATUS",
            "",
            None,
            "sensor.gas_water_heater_override_status",
            "",
            id="empty_string",
        ),
        pytest.param(
            "@SIGNAL",
            {"value": -67},
            None,
            "sensor.gas_water_heater_wi_fi_signal",
            "-67",
            id="wifi",
        ),
    ],
)
async def test_sensor_discovery_and_updates(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
    mock_equipment: Equipment,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    field: str,
    value: dict | str,
    missing_value: dict | None,
    entity_id: str,
    expected: str,
) -> None:
    """Discover late values once and keep the entity when data becomes missing."""
    equipment_data.pop(field, None)
    await setup_integration()
    assert entity_registry.async_get(entity_id) is None

    mock_equipment.update_equipment_info({"device_name": "device_1", field: value})
    await hass.async_block_till_done()
    original = entity_registry.async_get(entity_id)
    assert original is not None
    assert hass.states.get(entity_id).state == expected
    entry_count = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    mock_equipment.update_equipment_info(
        {"device_name": "device_1", field: missing_value}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id).id == original.id
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    mock_equipment.update_equipment_info({"device_name": "device_1", field: value})
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id).id == original.id
    assert hass.states.get(entity_id).state == expected
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == entry_count
    )


async def test_late_wifi_disabled_by_default(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    equipment_data: dict,
    mock_equipment: Equipment,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep Wi-Fi disabled when its first value arrives after setup."""
    del equipment_data["@SIGNAL"]
    await setup_integration()
    entity_id = "sensor.gas_water_heater_wi_fi_signal"
    assert entity_registry.async_get(entity_id) is None

    mock_equipment.update_equipment_info(
        {"device_name": "device_1", "@SIGNAL": {"value": -67}}
    )
    await hass.async_block_till_done()
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


async def test_discovery_stops_on_unload(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_config_entry: MockConfigEntry,
    mock_equipment: Equipment,
    entity_registry: er.EntityRegistry,
) -> None:
    """Stop discovering sensors when the integration is unloaded."""
    await setup_integration()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_equipment.update_equipment_info(
        {"device_name": "device_1", "@TANK": {"value": 90}}
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.gas_water_heater_tank_health") is None


@pytest.mark.parametrize("additional_platforms", [[Platform.WATER_HEATER]])
async def test_usage_discovery_after_poll(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[None]],
    mock_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Discover usage sensors from polled reports without requiring an MQTT update."""
    mock_api.get_dynamic_action.side_effect = InvalidResponseFormat
    await setup_integration()
    energy_entity = "sensor.gas_water_heater_energy_usage_today"
    water_entity = "sensor.gas_water_heater_water_usage_today"
    assert entity_registry.async_get(energy_entity) is None
    assert entity_registry.async_get(water_entity) is None

    energy = await async_load_json_object_fixture(hass, "energy_usage.json", DOMAIN)
    water = await async_load_json_object_fixture(hass, "water_usage.json", DOMAIN)
    mock_api.get_dynamic_action.side_effect = [energy, water]
    await async_update_entity(hass, "water_heater.gas_water_heater")
    await hass.async_block_till_done()
    original = entity_registry.async_get(energy_entity)
    assert original is not None
    assert hass.states.get(energy_entity).state == "2.93"
    water_state = hass.states.get(water_entity)
    assert float(water_state.state) == pytest.approx(18.92705892)
    assert water_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.LITERS

    energy["results"]["energy_usage"]["data"] = []
    mock_api.get_dynamic_action.side_effect = [energy, water]
    await async_update_entity(hass, "water_heater.gas_water_heater")
    await hass.async_block_till_done()
    assert entity_registry.async_get(energy_entity).id == original.id
    assert hass.states.get(energy_entity).state == STATE_UNKNOWN
