"""Tests for the Nobø Ecohub sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import entity_unique_ids, fire_hub_update

from tests.common import MockConfigEntry, snapshot_platform

TEMPERATURE_ENTITY = "sensor.living_room_floor_sensor_temperature"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the sensor platform for these tests."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """All sensor entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_temperature_unknown_when_missing(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Missing temperature values surface as unknown state."""
    mock_nobo_hub.get_current_component_temperature.return_value = None
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(TEMPERATURE_ENTITY).state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_temperature_push_update(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Pushed hub updates refresh the temperature state."""
    assert hass.states.get(TEMPERATURE_ENTITY).state == "21.5"

    mock_nobo_hub.get_current_component_temperature.return_value = "19.3"
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(TEMPERATURE_ENTITY).state == "19.3"


@pytest.mark.usefixtures("init_integration")
async def test_component_removed_removes_entity(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Removing a component via the Nobø app must not crash and removes the entity."""
    mock_nobo_hub.components.pop("200000059091")
    await fire_hub_update(hass, mock_nobo_hub)
    assert hass.states.get(TEMPERATURE_ENTITY) is None


@pytest.mark.usefixtures("init_integration")
async def test_readded_component_reappears(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A component removed and re-added under the same serial (the hub reuses serials) reappears."""
    entry_id = mock_config_entry.entry_id
    serial = "200000059092"
    model = MagicMock()
    model.name = "Panel heater"
    model.has_temp_sensor = True
    component = {
        "serial": serial,
        "name": "Bedroom sensor",
        "zone_id": "1",
        "model": model,
    }

    mock_nobo_hub.components[serial] = component
    await fire_hub_update(hass, mock_nobo_hub)
    assert serial in entity_unique_ids(entity_registry, entry_id)

    del mock_nobo_hub.components[serial]
    await fire_hub_update(hass, mock_nobo_hub)
    assert serial not in entity_unique_ids(entity_registry, entry_id)

    mock_nobo_hub.components[serial] = component
    await fire_hub_update(hass, mock_nobo_hub)
    assert serial in entity_unique_ids(entity_registry, entry_id)


@pytest.mark.parametrize(
    ("has_temp_sensor", "present"),
    [(True, True), (False, False)],
    ids=["temp_sensor", "no_temp_sensor"],
)
@pytest.mark.usefixtures("init_integration")
async def test_new_component_added(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    has_temp_sensor: bool,
    present: bool,
) -> None:
    """A component yields a sensor only when it has a temperature sensor."""
    entry_id = mock_config_entry.entry_id
    serial = "200000059092"
    model = MagicMock()
    model.name = "Panel heater"
    model.has_temp_sensor = has_temp_sensor
    mock_nobo_hub.components[serial] = {
        "serial": serial,
        "name": "Bedroom sensor",
        "zone_id": "1",
        "model": model,
    }
    await fire_hub_update(hass, mock_nobo_hub)

    assert (serial in entity_unique_ids(entity_registry, entry_id)) is present
