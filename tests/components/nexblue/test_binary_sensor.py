"""Tests for NexBlue binary sensors."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from nexblue_api import NexBlueConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CHARGER_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit this module's setup to the binary sensor platform."""
    with patch("homeassistant.components.nexblue.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


async def test_binary_sensor_entities_snapshot(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the complete NexBlue binary sensor platform through a snapshot."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        init_integration.entry_id,
    )


async def test_cable_lock_state_is_on_when_charger_is_unlocked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test cable lock state is on when the cable is unlocked."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS, is_lock=False
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.nb123456_cable_lock_state").state == "on"


async def test_charging_enabled_is_off_when_charger_is_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test charging enabled is off when the charger is disabled."""
    mock_client.async_get_charger_status.return_value = replace(
        CHARGER_STATUS, is_disable=True
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.nb123456_charging_enabled").state == "off"


async def test_binary_sensors_unavailable_when_coordinator_update_fails(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed coordinator update makes binary sensors unavailable."""
    mock_client.async_list_chargers.side_effect = NexBlueConnectionError

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.nb123456_cable_lock_state").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("binary_sensor.nb123456_charging_enabled").state
        == STATE_UNAVAILABLE
    )
