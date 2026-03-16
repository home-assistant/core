"""Test init of Tractive integration."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aiotractive.exceptions import TractiveError, UnauthorizedError
import pytest

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.tractive.const import (
    ATTR_DAILY_GOAL,
    ATTR_MINUTES_ACTIVE,
    ATTR_MINUTES_DAY_SLEEP,
    ATTR_MINUTES_NIGHT_SLEEP,
    ATTR_MINUTES_REST,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    with patch("homeassistant.components.tractive.TractiveClient.unsubscribe"):
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    ("method", "exc", "entry_state"),
    [
        ("authenticate", UnauthorizedError, ConfigEntryState.SETUP_ERROR),
        ("authenticate", TractiveError, ConfigEntryState.SETUP_RETRY),
        ("trackable_objects", TractiveError, ConfigEntryState.SETUP_RETRY),
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


async def test_config_not_ready(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for setup failure if the tracker_details doesn't contain '_id'."""
    mock_tractive_client.tracker.return_value.details.return_value.pop("_id")

    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_trackable_without_details(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a successful setup entry."""
    mock_tractive_client.trackable_objects.return_value[0].details.return_value = {
        "device_id": "xyz098"
    }

    await init_integration(hass, mock_config_entry)

    assert (
        "Tracker xyz098 has no details and will be skipped. This happens for shared trackers"
        in caplog.text
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_trackable_without_device_id(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry."""
    mock_tractive_client.trackable_objects.return_value[0].details.return_value = {
        "device_id": None
    }

    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unsubscribe_on_ha_stop(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unsuscribe when HA stops."""
    await init_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.tractive.TractiveClient.unsubscribe"
    ) as mock_unsuscribe:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_unsuscribe.called


async def test_server_unavailable(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    entity_id = "sensor.test_pet_tracker_battery"

    await init_integration(hass, mock_config_entry)

    # send event to make the entity available
    mock_tractive_client.send_hardware_event(mock_config_entry)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # send server unavailable event, the entity should be unavailable
    mock_tractive_client.send_server_unavailable_event(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # send event to make the entity available once again
    mock_tractive_client.send_hardware_event(mock_config_entry)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


@pytest.mark.parametrize(("sleep_data"), [None, {}, {"unexpected": 123}])
async def test_missing_sleep_data(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sleep_data: dict[str, Any] | None,
) -> None:
    """Test for missing sleep data."""
    event = {"petId": "pet_id_123", "sleep": sleep_data}

    await init_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.tractive.async_dispatcher_send"
    ) as async_dispatcher_send_mock:
        mock_tractive_client.send_health_overview_event(mock_config_entry, event)

    assert async_dispatcher_send_mock.call_count == 1
    payload = async_dispatcher_send_mock.mock_calls[0][1][2]
    assert payload[ATTR_MINUTES_DAY_SLEEP] is None
    assert payload[ATTR_MINUTES_NIGHT_SLEEP] is None
    assert payload[ATTR_MINUTES_REST] is None


@pytest.mark.parametrize(("activity_data"), [None, {}, {"unexpected": 123}])
async def test_missing_activity_data(
    hass: HomeAssistant,
    mock_tractive_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    activity_data: dict[str, Any] | None,
) -> None:
    """Test for missing activity data."""
    event = {"petId": "pet_id_123", "activity": activity_data}

    await init_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.tractive.async_dispatcher_send"
    ) as async_dispatcher_send_mock:
        mock_tractive_client.send_health_overview_event(mock_config_entry, event)

    assert async_dispatcher_send_mock.call_count == 1
    payload = async_dispatcher_send_mock.mock_calls[0][1][2]
    assert payload[ATTR_DAILY_GOAL] is None
    assert payload[ATTR_MINUTES_ACTIVE] is None


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
