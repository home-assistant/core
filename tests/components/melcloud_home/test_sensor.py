"""Tests for the MELCloud Home sensor platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aiomelcloudhome import UserContext
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.components.melcloud_home.coordinator import TELEMETRY_UPDATE_INTERVAL
from homeassistant.components.sensor import ATTR_LAST_RESET
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)

OPERATION_STATUS_ENTITY_ID = "sensor.heat_pump_operation_status"
OUTDOOR_TEMPERATURE_ENTITY_ID = "sensor.living_room_ac_outdoor_temperature"


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_melcloud_client")
@pytest.mark.freeze_time("2026-06-08 12:00:00+00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("operation_mode", "expected_state"),
    [
        pytest.param("Stop", "idle", id="idle"),
        pytest.param("HotWater", "heating_water", id="heating_water"),
        pytest.param("Heat", "heating_zones", id="heat"),
        pytest.param("HeatZones", "heating_zones", id="heating_zones"),
        pytest.param("Cool", "cooling", id="cool"),
        pytest.param("Heating", "heating_zones", id="heating"),
        pytest.param("FreezeStat", "heating_zones", id="freeze_stat"),
        pytest.param("Cooling", "cooling", id="cooling"),
        pytest.param("Defrost", STATE_UNKNOWN, id="unsupported_mode"),
    ],
)
async def test_operation_status(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    operation_mode: str,
    expected_state: str,
) -> None:
    """Test the operation status follows the unit's operation mode."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    settings = {
        unit_setting["name"]: unit_setting
        for unit_setting in context["buildings"][0]["airToWaterUnits"][0]["settings"]
    }
    settings["OperationMode"]["value"] = operation_mode
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(OPERATION_STATUS_ENTITY_ID))
    assert state.state == expected_state


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("sensor.living_room_ac_energy_consumed_monthly", id="ata"),
        pytest.param("sensor.heat_pump_energy_consumed_monthly", id="atw"),
    ],
)
@pytest.mark.freeze_time("2026-06-30 23:58:00+00:00")
async def test_energy_last_reset_month_rollover(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test last_reset only moves to the new month once its energy is fetched."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_LAST_RESET] == "2026-06-01T00:00:00+00:00"

    # The main coordinator writes the June total again after midnight
    mock_melcloud_client.get_energy_telemetry.reset_mock()
    freezer.move_to("2026-07-01 00:01:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_melcloud_client.get_energy_telemetry.assert_not_called()
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_LAST_RESET] == "2026-06-01T00:00:00+00:00"

    # The telemetry coordinator refreshes 15 minutes after setup
    freezer.move_to("2026-07-01 00:13:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_melcloud_client.get_energy_telemetry.call_args.kwargs[
        "from_dt"
    ] == datetime(2026, 7, 1, tzinfo=UTC)
    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_LAST_RESET] == "2026-07-01T00:00:00+00:00"


async def test_outdoor_temperature_sensor_added_when_reported(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the outdoor temperature sensor is only added once the unit reports one."""
    mock_melcloud_client.get_outdoor_temperature.return_value = None
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(OUTDOOR_TEMPERATURE_ENTITY_ID) is None

    mock_melcloud_client.get_outdoor_temperature.return_value = 19.5
    freezer.tick(TELEMETRY_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(OUTDOOR_TEMPERATURE_ENTITY_ID))
    assert state.state == "19.5"


async def test_outdoor_temperature_not_fetched_without_sensor(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test units reporting no outdoor temperature sensor are not probed."""
    context = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    context["buildings"][0]["airToAirUnits"][0]["capabilities"][
        "hasOutdoorTemperatureSensor"
    ] = False
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(context)

    await setup_integration(hass, mock_config_entry)

    mock_melcloud_client.get_outdoor_temperature.assert_not_called()
    assert hass.states.get(OUTDOOR_TEMPERATURE_ENTITY_ID) is None
