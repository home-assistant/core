"""Test the Vitesy binary sensor platform."""

from unittest.mock import AsyncMock, patch

from aiovitesy.api import VitesyDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vitesy.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

BATTERY_CHARGING = "binary_sensor.kitchen_shelfy_charging"


def _set_charging(device: VitesyDevice, value: object) -> None:
    """Replace the charging reading in the device's status data."""
    device.measurement = {
        **device.measurement,
        "status_data": [{"id": "charging", "value": value}],
    }


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.vitesy.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("value", "state"),
    [
        pytest.param(True, STATE_ON, id="charging"),
        pytest.param("yes", STATE_UNKNOWN, id="non_boolean"),
    ],
)
async def test_battery_charging_update(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
    freezer: FrozenDateTimeFactory,
    value: object,
    state: str,
) -> None:
    """Test the charging state follows the latest status data."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(BATTERY_CHARGING).state == STATE_OFF

    _set_charging(mock_devices[DEVICE_ID], value)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_CHARGING).state == state


async def test_battery_charging_not_created_when_not_reported(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
) -> None:
    """Test no charging entity is created for a device that doesn't report it."""
    mock_devices[DEVICE_ID].measurement = {"score": 0.5}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(BATTERY_CHARGING) is None
