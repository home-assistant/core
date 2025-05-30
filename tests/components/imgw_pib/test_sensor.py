"""Test the IMGW-PIB sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from imgw_pib import ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imgw_pib.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_PLATFORM
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.river_name_station_name_water_level"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_imgw_pib_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.imgw_pib.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imgw_pib_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "526.0"

    mock_imgw_pib_client.get_hydrological_data.side_effect = ApiError("API Error")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_imgw_pib_client.get_hydrological_data.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "526.0"


async def test_remove_entity(
    hass: HomeAssistant,
    mock_imgw_pib_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing entity."""
    entity_id = "sensor.river_name_station_name_flood_alarm_level"
    mock_config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        SENSOR_PLATFORM,
        DOMAIN,
        "123_flood_alarm_level",
        suggested_object_id=entity_id.rsplit(".", maxsplit=1)[-1],
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
