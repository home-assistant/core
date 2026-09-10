"""Tests for the Guntamatic sensor platform."""

from datetime import datetime, timedelta
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
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import MOCK_PARSE_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_heater")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    # The service date sensor computes now() + a day count; freeze the clock
    # so the snapshot does not depend on the day the tests run on.
    freezer.move_to("2030-01-01 12:00:00+00:00")
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
        pytest.param("extra_dhw_boost", TRANSLATE_PUMP_MODE, id="extra_dhw_boost"),
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
        assert f"{prefix}{option}" in translations


async def test_enum_sensor_unmapped_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test an unmapped enum value is exposed as unknown instead of raising."""
    return_value = MOCK_PARSE_DATA.copy()
    return_value["heating_circulation_pump_1"] = ["BROKEN", ""]
    mock_heater.parse_data.return_value = return_value

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.heating_circuit_1_pump")
    assert state is not None
    assert state.state == STATE_UNKNOWN


_SERIAL = "959103"


@pytest.mark.usefixtures("mock_heater")
async def test_heating_circuit_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test circuit sub-devices link to the main unit and absent slots create none."""
    await setup_integration(hass, mock_config_entry)

    main = device_registry.async_get_device_by_identifier(
        (DOMAIN, _SERIAL), mock_config_entry.entry_id
    )
    circuit = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{_SERIAL}_hc1"), mock_config_entry.entry_id
    )
    assert main is not None
    assert circuit is not None
    assert circuit.parent_device_id == main.id
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{_SERIAL}_hc2"), mock_config_entry.entry_id
        )
        is None
    )


async def test_key_disappearing_makes_entity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test an individual sensor becoming unavailable when its key disappears."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.mock_title_boiler_temperature"
    assert hass.states.get(entity_id).state == "14.09"

    # Simulate the heater no longer reporting this key
    reduced = {k: v for k, v in MOCK_PARSE_DATA.items() if k != "boiler_temperature"}
    mock_heater.parse_data.return_value = reduced
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    # Restore the key and verify the entity recovers
    mock_heater.parse_data.return_value = MOCK_PARSE_DATA.copy()
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "14.09"


async def test_service_date_fractional_days(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Fractional service_days roll over correctly when time is not midnight."""
    frozen = datetime(2026, 8, 26, 15, 00, tzinfo=dt_util.get_default_time_zone())
    freezer.move_to(frozen)

    data = MOCK_PARSE_DATA.copy()
    data["service_days"] = ["1.5", "d"]
    mock_heater.parse_data.return_value = data

    await setup_integration(hass, mock_config_entry)
    entity_registry.async_update_entity(
        "sensor.mock_title_service_date", disabled_by=None
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.mock_title_service_date")
    assert state is not None
    assert state.state == (frozen + timedelta(days=1.5)).date().isoformat()
