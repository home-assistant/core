"""Tests for the Guntamatic sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from guntamatic.heater import (
    TRANSLATE_HC_PROGRAM,
    TRANSLATE_PUMP_MODE,
    NoSerialException,
)
import pytest
import requests
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.guntamatic.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.guntamatic.sensor import GUNTAMATIC_SENSORS
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_heater")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.guntamatic._PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    disabled_entries = [
        entity_entry
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entity_entry.disabled_by is not None
    ]
    assert disabled_entries
    assert all(
        entity_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
        for entity_entry in disabled_entries
    )
    for entity_entry in disabled_entries:
        entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


@pytest.mark.parametrize(
    "side_effect",
    [
        requests.exceptions.ConnectionError("Connection lost"),
        NoSerialException,
        Exception("Unknown error"),
    ],
)
async def test_state_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    side_effect: Exception,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors handle failures."""
    await setup_integration(hass, mock_config_entry)

    mock_heater.parse_data.side_effect = side_effect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_title_boiler_temperature")
    assert state.state == STATE_UNAVAILABLE

    # Recovery
    mock_heater.parse_data.side_effect = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.mock_title_boiler_temperature")
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("key_prefix", "translation_table"),
    [
        pytest.param("heating_circulation_program", TRANSLATE_HC_PROGRAM, id="program"),
        pytest.param(
            "heating_circulation_pump",
            TRANSLATE_PUMP_MODE,
            id="heating_circulation_pump",
        ),
        pytest.param("auxiliary_pump", TRANSLATE_PUMP_MODE, id="auxiliary_pump"),
    ],
)
def test_enum_options_match_library(
    key_prefix: str,
    translation_table: dict[str, str],
) -> None:
    """Test enum options mirror the canonical values emitted by the library."""
    option_sets = {
        tuple(description.options)
        for description in GUNTAMATIC_SENSORS
        if description.key.startswith(key_prefix)
        and description.device_class is SensorDeviceClass.ENUM
    }
    assert len(option_sets) == 1, f"Inconsistent options across {key_prefix} sensors"
    assert set(option_sets.pop()) == set(translation_table.values())


enum_descriptions = [
    description
    for description in GUNTAMATIC_SENSORS
    if description.device_class is SensorDeviceClass.ENUM
]


@pytest.mark.parametrize(
    "description",
    enum_descriptions,
    ids=lambda description: description.key,
)
async def test_enum_states_translated(
    hass: HomeAssistant,
    description: SensorEntityDescription,
) -> None:
    """Test every option of an enum sensor has a state translation."""
    translations = await async_get_translations(hass, "en", "entity", [DOMAIN])
    prefix = f"component.{DOMAIN}.entity.sensor.{description.translation_key}.state."
    for option in description.options:
        assert f"{prefix}{option}.name" in translations
