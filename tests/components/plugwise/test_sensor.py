"""Tests for the Plugwise Sensor integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_sensor_entities(
    hass: HomeAssistant,
    mock_smile_adam: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_climate_sensor_humidity(
    hass: HomeAssistant,
    mock_smile_adam_jip: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of climate related humidity sensor entity."""
    state = hass.states.get("sensor.woonkamer_humidity")
    assert state
    assert float(state.state) == 56.2


async def test_unique_id_migration_humidity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_smile_adam_jip: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unique ID migration of -relative_humidity to -humidity."""
    mock_config_entry.add_to_hass(hass)

    # Entry to migrate
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "f61f1a2535f54f52ad006a3d18e459ca-relative_humidity",
        config_entry=mock_config_entry,
        suggested_object_id="woonkamer_humidity",
        disabled_by=None,
    )
    # Entry not needing migration
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "f61f1a2535f54f52ad006a3d18e459ca-battery",
        config_entry=mock_config_entry,
        suggested_object_id="woonkamer_battery",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.woonkamer_humidity") is not None
    assert hass.states.get("sensor.woonkamer_battery") is not None

    entity_entry = entity_registry.async_get("sensor.woonkamer_humidity")
    assert entity_entry
    assert entity_entry.unique_id == "f61f1a2535f54f52ad006a3d18e459ca-humidity"

    entity_entry = entity_registry.async_get("sensor.woonkamer_battery")
    assert entity_entry
    assert entity_entry.unique_id == "f61f1a2535f54f52ad006a3d18e459ca-battery"


@pytest.mark.parametrize("chosen_env", ["anna_heatpump_heating"], indirect=True)
@pytest.mark.parametrize("cooling_present", [True], indirect=True)
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_anna_sensor_states(
    hass: HomeAssistant,
    mock_smile_anna: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Anna sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["p1v4_442_single"], indirect=True)
@pytest.mark.parametrize("gateway_id", ["a455b61e52394b2db5081ce025a430f3"], indirect=True)
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_p1_dsmr_sensor_entities(
    hass: HomeAssistant,
    mock_smile_p1: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test P1 1-phase sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["p1v4_442_triple"], indirect=True)
@pytest.mark.parametrize("gateway_id", ["03e65b16e4b247a29ae0d75a78cb492e"], indirect=True)
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_p1_3ph_dsmr_sensor_entities(
    hass: HomeAssistant,
    mock_smile_p1: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test P1 3-phase sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("chosen_env", ["p1v4_442_triple"], indirect=True)
@pytest.mark.parametrize(
    "gateway_id", ["03e65b16e4b247a29ae0d75a78cb492e"], indirect=True
)
async def test_p1_3ph_dsmr_sensor_disabled_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_smile_p1: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test disabled power related sensor entities intent."""
    state = hass.states.get("sensor.p1_voltage_phase_one")
    assert not state

    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.p1_voltage_phase_one")
    assert state
    assert float(state.state) == 233.2


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stretch_sensor_entities(
    hass: HomeAssistant,
    mock_stretch: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Stretch sensor snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)
