"""Test the Vitesy sensor platform."""

from unittest.mock import AsyncMock, patch

from aiovitesy.api import VitesyDevice
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform

AIR_QUALITY_SCORE = "sensor.kitchen_shelfy_air_quality_score"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.vitesy.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_unavailable_when_device_disconnected(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
) -> None:
    """Test sensors go unavailable when the device reports as disconnected."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(AIR_QUALITY_SCORE).state == "49"

    mock_devices[DEVICE_ID].connected = False
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(AIR_QUALITY_SCORE).state == STATE_UNAVAILABLE


async def test_air_quality_score_without_value(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
) -> None:
    """Test the score sensor reports unknown when the measurement drops it."""
    await setup_integration(hass, mock_config_entry)

    mock_devices[DEVICE_ID].measurement = {
        **mock_devices[DEVICE_ID].measurement,
        "score": None,
    }
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(AIR_QUALITY_SCORE).state == STATE_UNKNOWN


async def test_sensors_absent_from_measurement_are_not_created(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
) -> None:
    """Test only the readings the device actually reports become entities."""
    device = mock_devices[DEVICE_ID]
    device.measurement = {"score": 0.5}
    device.maintenance = {}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(AIR_QUALITY_SCORE) is not None
    for absent in (
        "battery",
        "fridge_temperature",
        "door_openings",
        "door_open_duration",
        "filter_change_due",
        "fridge_cleaning_due",
    ):
        assert hass.states.get(f"sensor.kitchen_shelfy_{absent}") is None
