"""Tests for the Gatus binary sensor platform."""

import json
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from gatus_api.client import GatusClientError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


async def test_binary_sensor_setup_and_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test standard successful setup and entity snapshots using snapshot_platform."""
    entity_registry = er.async_get(hass)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_binary_sensor_dynamic_update(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the binary sensor entity updates when the mock client returns new data."""
    state = hass.states.get("binary_sensor.core_backend_service")
    assert state is not None
    assert state.state == "on"

    fixture_data = await hass.async_add_executor_job(load_fixture, "gatus/group.json")
    mock_data = json.loads(fixture_data)

    mock_gatus_client.get_endpoints_statuses.return_value = mock_data

    freezer.tick(300)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.core_backend_service")
    assert state.state == "off"


async def test_binary_sensor_no_group(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
) -> None:
    """Test that the binary sensor entity is created correctly when an endpoint has no group."""
    fixture_data = await hass.async_add_executor_job(
        load_fixture, "gatus/no_group.json"
    )
    mock_data = json.loads(fixture_data)

    mock_gatus_client.get_endpoints_statuses.return_value = mock_data

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://gatus.example.com:80"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.backend_service")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_client_error(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a client exception cleanly marks entities as unavailable."""
    state = hass.states.get("binary_sensor.core_backend_service")
    assert state is not None
    assert state.state == "on"

    mock_gatus_client.get_endpoints_statuses.side_effect = GatusClientError

    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.core_backend_service")
    assert state.state == "unavailable"
