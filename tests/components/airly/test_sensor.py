"""Test sensor of Airly integration."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from airly.exceptions import AirlyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.airly.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("mock_airly_client")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    await init_integration(hass, mock_config_entry)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


@pytest.mark.parametrize(
    "exception",
    [
        AirlyError(HTTPStatus.NOT_FOUND, {"message": "Not found"}),
        TimeoutError(),
    ],
)
async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
) -> None:
    """Ensure that we mark the entities unavailable correctly.

    Test when service is offline.
    """
    await init_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"

    mock_airly_client.create_measurements_session_point.return_value.update.side_effect = AirlyError(
        HTTPStatus.NOT_FOUND, {"message": "Not found"}
    )
    future = utcnow() + timedelta(minutes=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_airly_client.create_measurements_session_point.return_value.update.side_effect = None
    future = utcnow() + timedelta(minutes=120)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_humidity")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "68.35"


async def test_manual_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass, mock_config_entry)

    call_count = mock_airly_client.create_measurements_session_point.call_count
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.home_humidity"]},
        blocking=True,
    )

    assert (
        mock_airly_client.create_measurements_session_point.call_count == call_count + 1
    )
