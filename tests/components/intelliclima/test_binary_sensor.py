"""Test IntelliClima Binary Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from pyintelliclima.intelliclima_types import IntelliClimaFilterStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def setup_intelliclima_binary_sensor_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the binary sensor platform."""
    with (
        patch(
            "homeassistant.components.intelliclima.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
    ):
        await setup_integration(hass, mock_config_entry)
        yield


async def test_all_binary_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    binary_sensor_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == BINARY_SENSOR_DOMAIN
    ]
    assert len(binary_sensor_entries) == 1

    for entity_entry in binary_sensor_entries:
        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry == snapshot


async def test_filter_cleaning_unavailable_when_tracking_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test the filter_cleaning sensor is unavailable when the vendor disables filter tracking.

    The vendor API keeps returning `change_filter: false` in this state, which
    would otherwise misreport a "clean filter" the integration can't actually vouch for.
    """
    mock_cloud_interface.get_filter_status.return_value = IntelliClimaFilterStatus(
        serial="11223344",
        is_active=False,
        from_date="2025-11-18 10:22:51",
        stats=[],
        totale=0,
        change_filter=False,
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_vmc_filter_cleaning_required")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
