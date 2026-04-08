"""Test the Teleinfo sensor platform."""

from unittest.mock import MagicMock

import pytest
import serial
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.teleinfo.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    MOCK_DECODED_DATA_BASE,
    MOCK_DECODED_DATA_EJP,
    MOCK_DECODED_DATA_HC,
)

from tests.common import MockConfigEntry, snapshot_platform

ADCO = "021861348497"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot test all sensor entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_setup_tempo(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test Tempo sensor entities are created with correct states."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    expected_values: dict[str, str] = {
        f"{ADCO}_blue_day_off_peak_index": "18328702",
        f"{ADCO}_blue_day_peak_index": "23739545",
        f"{ADCO}_white_day_off_peak_index": "1466099",
        f"{ADCO}_white_day_peak_index": "2132883",
        f"{ADCO}_red_day_off_peak_index": "860118",
        f"{ADCO}_red_day_peak_index": "844115",
        f"{ADCO}_apparent_power": "2830",
        f"{ADCO}_current_tariff_period": "off_peak_blue_day",
    }

    # These sensors are disabled by default; verify they are registered but have no state
    disabled_unique_ids = [
        f"{ADCO}_instantaneous_current",
        f"{ADCO}_tomorrow_color",
    ]
    for unique_id in disabled_unique_ids:
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"Entity with unique_id {unique_id} not found"
        state = hass.states.get(entity_id)
        assert state is None, f"Disabled entity {unique_id} should have no state"

    for unique_id, expected_state in expected_values.items():
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"Entity with unique_id {unique_id} not found"
        state = hass.states.get(entity_id)
        assert state is not None, f"State for {entity_id} not found"
        assert state.state == expected_state, (
            f"Expected {expected_state} for {unique_id}, got {state.state}"
        )

    # Verify BASE/HC/EJP sensors are NOT created
    for absent_unique_id in (
        f"{ADCO}_base_index",
        f"{ADCO}_off_peak_index",
        f"{ADCO}_peak_index",
        f"{ADCO}_normal_hours_index",
        f"{ADCO}_peak_mobile_hours_index",
        f"{ADCO}_ejp_warning",
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, absent_unique_id
        )
        assert entity_id is None, (
            f"Entity {absent_unique_id} should not exist for Tempo contract"
        )


async def test_sensor_setup_base(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test BASE contract creates only the base index sensor."""
    mock_teleinfo.decode.return_value = MOCK_DECODED_DATA_BASE
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # BASE sensor should exist
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ADCO}_base_index"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "45367891"

    # Common sensors should exist
    for unique_id in (f"{ADCO}_apparent_power", f"{ADCO}_current_tariff_period"):
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"Common sensor {unique_id} not found"

    # Tempo/HC/EJP sensors should NOT exist
    for absent_unique_id in (
        f"{ADCO}_blue_day_off_peak_index",
        f"{ADCO}_off_peak_index",
        f"{ADCO}_normal_hours_index",
        f"{ADCO}_tomorrow_color",
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, absent_unique_id
        )
        assert entity_id is None, (
            f"Entity {absent_unique_id} should not exist for BASE contract"
        )


async def test_sensor_setup_hc(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test HC contract creates off-peak and peak index sensors."""
    mock_teleinfo.decode.return_value = MOCK_DECODED_DATA_HC
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # HC sensors should exist
    expected_values: dict[str, str] = {
        f"{ADCO}_off_peak_index": "25643781",
        f"{ADCO}_peak_index": "31285904",
        f"{ADCO}_apparent_power": "2830",
        f"{ADCO}_current_tariff_period": "off_peak",
    }
    for unique_id, expected_state in expected_values.items():
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"Entity with unique_id {unique_id} not found"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    # BASE/Tempo/EJP sensors should NOT exist
    for absent_unique_id in (
        f"{ADCO}_base_index",
        f"{ADCO}_blue_day_off_peak_index",
        f"{ADCO}_normal_hours_index",
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, absent_unique_id
        )
        assert entity_id is None


async def test_sensor_setup_ejp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test EJP contract creates normal hours and peak mobile sensors."""
    mock_teleinfo.decode.return_value = MOCK_DECODED_DATA_EJP
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # EJP sensors should exist
    expected_values: dict[str, str] = {
        f"{ADCO}_normal_hours_index": "38912456",
        f"{ADCO}_peak_mobile_hours_index": "7654321",
        f"{ADCO}_apparent_power": "2830",
        f"{ADCO}_current_tariff_period": "normal_hours",
    }
    for unique_id, expected_state in expected_values.items():
        entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, f"Entity with unique_id {unique_id} not found"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    # EJP warning is disabled by default
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ADCO}_ejp_warning"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is None  # disabled, no state

    # BASE/Tempo/HC sensors should NOT exist
    for absent_unique_id in (
        f"{ADCO}_base_index",
        f"{ADCO}_blue_day_off_peak_index",
        f"{ADCO}_off_peak_index",
        f"{ADCO}_tomorrow_color",
    ):
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, absent_unique_id
        )
        assert entity_id is None


async def test_sensor_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test the device is registered correctly."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, ADCO)})
    assert device is not None
    assert device.name == f"Teleinfo {ADCO}"
    assert device.manufacturer == "Enedis"


async def test_sensor_unique_ids_tempo(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test sensor unique IDs for Tempo contract follow the expected pattern."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    expected_unique_ids = [
        f"{ADCO}_blue_day_off_peak_index",
        f"{ADCO}_blue_day_peak_index",
        f"{ADCO}_white_day_off_peak_index",
        f"{ADCO}_white_day_peak_index",
        f"{ADCO}_red_day_off_peak_index",
        f"{ADCO}_red_day_peak_index",
        f"{ADCO}_apparent_power",
        f"{ADCO}_instantaneous_current",
        f"{ADCO}_current_tariff_period",
        f"{ADCO}_tomorrow_color",
    ]

    for unique_id in expected_unique_ids:
        entry = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entry is not None, f"Entity with unique_id {unique_id} not found"


async def test_sensor_unavailable_on_serial_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test sensors become unavailable when the dongle disconnects."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ADCO}_apparent_power"
    )
    assert entity_id is not None

    # Verify sensor is available initially
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2830"

    # Simulate serial error on next update
    mock_serial_port.side_effect = serial.SerialException("device disconnected")
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_recovers_after_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test sensors recover when the dongle reconnects after an error."""
    from .conftest import MOCK_FRAME  # noqa: PLC0415

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ADCO}_apparent_power"
    )
    assert entity_id is not None

    # Simulate serial error
    mock_serial_port.side_effect = serial.SerialException("device disconnected")
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate recovery
    mock_serial_port.side_effect = None
    mock_serial_port.return_value = MOCK_FRAME
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2830"


async def test_sensor_returns_unknown_on_missing_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test sensors return unknown when a label is missing from the frame."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ADCO}_apparent_power"
    )
    assert entity_id is not None

    # Verify sensor is available initially
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "2830"

    # Simulate a frame missing the PAPP key
    from .conftest import MOCK_DECODED_DATA, MOCK_FRAME  # noqa: PLC0415

    incomplete_data = {k: v for k, v in MOCK_DECODED_DATA.items() if k != "PAPP"}
    mock_teleinfo.decode.return_value = incomplete_data
    mock_serial_port.return_value = MOCK_FRAME

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
