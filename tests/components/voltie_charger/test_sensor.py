"""Tests for the Voltie Charger sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.voltie_charger.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import CHARGER_ID, status_fixture


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, CHARGER_ID), mock_config_entry.entry_id
    )
    assert device_entry
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    ):
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"cdr": None, "evse_state": 1}, "0"),
        ({"cdr": None, "evse_state": 2}, STATE_UNKNOWN),
        ({"evse_state": 1}, "5.852"),
    ],
    ids=["idle", "connected_without_session", "session"],
)
async def test_session_energy(
    hass: HomeAssistant,
    mock_voltie: MagicMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    overrides: dict[str, object],
    expected: str,
) -> None:
    """Test the session energy reads 0 while no car is connected."""
    mock_voltie.status.return_value = status_fixture(**overrides)
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.voltie_charger_4335_session_energy").state == expected
    )


async def test_unknown_evse_state(
    hass: HomeAssistant,
    mock_voltie: MagicMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the status is unknown before the first EVSE reading and for new codes."""
    entity_id = "sensor.voltie_charger_4335_status"
    for code in (0, 99):
        mock_voltie.status.return_value = status_fixture(evse_state=code)
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_no_meter_reading(
    hass: HomeAssistant,
    mock_voltie: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the total energy sensor needs firmware that reports the meter."""
    mock_voltie.status.return_value = replace(
        status_fixture(), meter_supported=False, meter_energy=None
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.voltie_charger_4335_total_energy") is None
    assert hass.states.get("sensor.voltie_charger_4335_session_energy") is not None
