"""Test the Teleinfo sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import serial
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.teleinfo.const import DOMAIN
from homeassistant.components.teleinfo.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_DECODED_DATA_BASE,
    MOCK_DECODED_DATA_EJP,
    MOCK_DECODED_DATA_HC,
    MOCK_DECODED_DATA_TEMPO,
    MOCK_FRAME,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ADCO = "021861348497"


@pytest.mark.parametrize(
    ("decoded_data", "contract"),
    [
        (MOCK_DECODED_DATA_BASE, "base"),
        (MOCK_DECODED_DATA_HC, "hc"),
        (MOCK_DECODED_DATA_EJP, "ejp"),
        (MOCK_DECODED_DATA_TEMPO, "tempo"),
    ],
    ids=["base", "hc", "ejp", "tempo"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    decoded_data: dict[str, str],
    contract: str,
) -> None:
    """Snapshot test all sensor entities for each supported contract type."""
    mock_teleinfo.decode.return_value = decoded_data
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("side_effect_attr", "side_effect"),
    [
        ("mock_serial_port", serial.SerialException("device disconnected")),
        ("mock_serial_port", TimeoutError("no data")),
    ],
    ids=["serial_error", "timeout"],
)
async def test_sensor_unavailable_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    side_effect_attr: str,
    side_effect: Exception,
) -> None:
    """Test sensors become unavailable on each failure mode at the next poll."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{ADCO}_PAPP")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "2830"

    # Trigger the configured failure on the next scheduled poll.
    mock_serial_port.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensor_unavailable_on_decode_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable on each failure mode at the next poll."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{ADCO}_PAPP")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "2830"

    mock_teleinfo.decode.side_effect = RuntimeError("bad frame")

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_sensor_recovers_after_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors recover when the dongle reconnects after an error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{ADCO}_PAPP")
    assert entity_id is not None

    # Simulate serial error on the next poll.
    mock_serial_port.side_effect = serial.SerialException("device disconnected")
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Simulate recovery on the following poll.
    mock_serial_port.side_effect = None
    mock_serial_port.return_value = MOCK_FRAME
    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "2830"


async def test_sensor_returns_unavailable_on_missing_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when a label is missing from the frame."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, f"{ADCO}_PAPP")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "2830"

    # Simulate a frame missing the PAPP key on the next poll.
    incomplete_data = {k: v for k, v in MOCK_DECODED_DATA_TEMPO.items() if k != "PAPP"}
    mock_teleinfo.decode.return_value = incomplete_data

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
