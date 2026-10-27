"""Snapshot tests for the Spin EV Charger sensors."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from spinev_ble import ChargerState
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import IDLE_STATUS, STATE_SENSOR


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Set up only the sensor platform."""
    with patch("homeassistant.components.spin_ble.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("mock_charger")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The sensor platform registers the entities it is expected to."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_out_of_service_is_a_state_not_unavailability(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_charger: AsyncMock
) -> None:
    """A charger that reports itself unavailable still answers, so its readings stay."""
    mock_charger.async_get_status.return_value = replace(
        IDLE_STATUS, state=ChargerState.UNAVAILABLE, state_value=10
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(STATE_SENSOR).state == "out_of_service"
    assert hass.states.get("sensor.123456789012_lifetime_energy").state == "1234.5"
