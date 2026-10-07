"""Test the Vitesy sensor platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aiovitesy.api import VitesyDevice
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vitesy.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

AIR_QUALITY_SCORE = "sensor.kitchen_shelfy_air_quality_score"
FILTER_CHANGE_DUE = "sensor.kitchen_shelfy_filter_change_due"
FRIDGE_TEMPERATURE = "sensor.kitchen_shelfy_fridge_temperature"


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors go unavailable when the device reports as disconnected."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(AIR_QUALITY_SCORE).state == "49.0458333333333"

    mock_devices[DEVICE_ID].connected = False
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(AIR_QUALITY_SCORE).state == STATE_UNAVAILABLE


async def test_air_quality_score_without_value(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the score sensor reports unknown when the measurement drops it."""
    await setup_integration(hass, mock_config_entry)

    mock_devices[DEVICE_ID].measurement = {
        **mock_devices[DEVICE_ID].measurement,
        "score": None,
    }
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(AIR_QUALITY_SCORE).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("attribute", "update", "entity_id", "warning"),
    [
        pytest.param(
            "measurement",
            {"sensors_data": [{"id": "TMP01-SY", "value": {"avg": "n/a"}}]},
            FRIDGE_TEMPERATURE,
            "Ignoring non-numeric value for reading TMP01-SY on Kitchen Shelfy: 'n/a'",
            id="reading_non_numeric_avg",
        ),
        pytest.param(
            "measurement",
            {"sensors_data": [{"id": "TMP01-SY", "value": "n/a"}]},
            FRIDGE_TEMPERATURE,
            "Ignoring non-numeric value for reading TMP01-SY on Kitchen Shelfy: 'n/a'",
            id="reading_non_numeric_scalar",
        ),
        pytest.param(
            "maintenance",
            {"filter": {"due_date": "not-a-date"}},
            FILTER_CHANGE_DUE,
            "Ignoring unparsable filter due date for Kitchen Shelfy: not-a-date",
            id="due_date_unparsable",
        ),
    ],
)
async def test_sensor_unknown_on_invalid_value(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_devices: dict[str, VitesyDevice],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    attribute: str,
    update: dict[str, Any],
    entity_id: str,
    warning: str,
) -> None:
    """Test a sensor reports unknown and warns when its value turns invalid."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(entity_id).state != STATE_UNKNOWN

    device = mock_devices[DEVICE_ID]
    setattr(device, attribute, {**getattr(device, attribute), **update})
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert warning in caplog.text


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
