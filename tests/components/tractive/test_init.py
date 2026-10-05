"""Test init of Tractive integration."""

from unittest.mock import AsyncMock

from aiotractive.exceptions import TractiveError, UnauthorizedError
import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.tractive.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry

BATTERY_ENTITY_ID = "sensor.tracker_device_id_123_battery"
ACTIVITY_ENTITY_ID = "sensor.test_pet_activity_time"


async def test_setup_entry(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_tractive_client.listen.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("method", "exc", "entry_state"),
    [
        ("async_fetch_trackables", UnauthorizedError, ConfigEntryState.SETUP_ERROR),
        ("async_fetch_trackables", TractiveError, ConfigEntryState.SETUP_RETRY),
        ("async_fetch_status", UnauthorizedError, ConfigEntryState.SETUP_ERROR),
        ("async_fetch_status", TractiveError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failed(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    exc: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test for setup failure."""
    getattr(mock_tractive_client, method).side_effect = exc

    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is entry_state


async def test_server_unavailable(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities become unavailable on a channel error and recover."""
    await init_integration(hass, mock_config_entry)

    # Initial value comes from the REST status
    assert hass.states.get(BATTERY_ENTITY_ID).state == "96"

    mock_tractive_client.send_error_event(TractiveError("Connection lost"))
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == STATE_UNAVAILABLE

    # The library notifies without an error once the channel reconnects
    mock_tractive_client.send_error_event(None)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "96"

    mock_tractive_client.set_tracker_status(
        battery_level=88,
        tracker_state="operational",
        power_saving=True,
        battery_charging=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == "88"


async def test_pet_without_health_data(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pet sensors are unavailable until health data arrives."""
    mock_tractive_client.status.pets.clear()

    await init_integration(hass, mock_config_entry)

    assert hass.states.get(ACTIVITY_ENTITY_ID).state == STATE_UNAVAILABLE

    mock_tractive_client.set_pet_status(
        daily_goal=200,
        minutes_active=150,
        minutes_day_sleep=100,
        minutes_night_sleep=300,
        minutes_rest=122,
    )
    await hass.async_block_till_done()

    assert hass.states.get(ACTIVITY_ENTITY_ID).state == "150"


async def test_reauth_on_unauthorized(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reauth flow is started when the channel reports an auth error."""
    await init_integration(hass, mock_config_entry)

    mock_tractive_client.send_error_event(UnauthorizedError())
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_ENTITY_ID).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize("sensor", ["activity_label", "calories", "sleep_label"])
async def test_remove_unsupported_sensor_entity(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    sensor: str,
) -> None:
    """Test removing unsupported sensor entity."""
    entity_id = f"sensor.test_pet_{sensor}"
    mock_config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"pet_id_123_{sensor}",
        suggested_object_id=entity_id.rsplit(".", maxsplit=1)[-1],
        config_entry=mock_config_entry,
    )

    await init_integration(hass, mock_config_entry)

    assert entity_registry.async_get(entity_id) is None
