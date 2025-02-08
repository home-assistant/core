"""Tests for the SMLIGHT sensor platform."""

from unittest.mock import MagicMock

from pysmlight import Sensors
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2024-07-01 00:00:00+00:00")
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the SMLIGHT sensors."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the disabled by default SMLIGHT sensors."""
    await setup_integration(hass, mock_config_entry)

    for sensor in ("core_uptime", "filesystem_usage", "ram_usage", "zigbee_uptime"):
        assert not hass.states.get(f"sensor.mock_title_{sensor}")

        assert (entry := entity_registry.async_get(f"sensor.mock_title_{sensor}"))
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zigbee_uptime_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test for uptime when zigbee socket is disconnected.

    In this case zigbee uptime state should be unknown.
    """
    mock_smlight_client.get_sensors.return_value = Sensors(socket_uptime=0)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.mock_title_zigbee_uptime")
    assert state.state == STATE_UNKNOWN
