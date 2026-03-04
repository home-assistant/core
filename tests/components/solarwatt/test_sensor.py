"""Test the Solarwatt sensor platform."""

from __future__ import annotations

from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.solarwatt.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_PAYLOAD, MOCK_USER_INPUT, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mocked config entry for Solarwatt."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
        unique_id="0004A20B000BF3A3",
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that all Solarwatt sensors are created correctly."""
    # Coordinator mit festem Payload patchen, damit keine echten HTTP-Calls passieren
    with (
        patch(
            "homeassistant.components.solarwatt.coordinator.SolarwattDataUpdateCoordinator._async_update_data",
            return_value=MOCK_PAYLOAD,
        ),
        patch(
            "homeassistant.components.solarwatt.PLATFORMS",
            [Platform.SENSOR],
        ),
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass,
            entity_registry,
            snapshot,
            mock_config_entry.entry_id,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "exception",
    [
        ClientError,
        TimeoutError,
        Exception,
    ],
)
async def test_refresh_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test that coordinator refresh errors are recorded."""
    # 1) Erstmal erfolgreiches Setup mit gültigem Payload
    with patch(
        "homeassistant.components.solarwatt.coordinator.SolarwattDataUpdateCoordinator._async_update_data",
        return_value=MOCK_PAYLOAD,
    ):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED

    # Sicherstellen, dass der Sensor initial einen Wert hat
    state = hass.states.get("sensor.sn_0004a20b000bf3a3_battery_state_of_charge")
    assert state is not None
    assert state.state == "42"

    # 2) Jetzt einen fehlgeschlagenen Refresh simulieren
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    coordinator = entry.runtime_data

    with patch(
        "homeassistant.components.solarwatt.coordinator.SolarwattDataUpdateCoordinator._async_update_data",
        side_effect=exception,
    ):
        await coordinator.async_request_refresh()
        await hass.async_block_till_done()

    # 3) Coordinator sollte den Fehlerzustand kennen
    assert coordinator.last_update_success is False

    # State kann weiterhin der letzte gültige Wert sein (hier: "42")
    state = hass.states.get("sensor.sn_0004a20b000bf3a3_battery_state_of_charge")
    assert state is not None
    assert state.state == "42"
