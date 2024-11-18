"""Tests for the Habitica binary sensor platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import ASSETS_URL, DEFAULT_URL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def binary_sensor_only() -> Generator[None]:
    """Enable only the binarty sensor platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


@pytest.mark.usefixtures("mock_habitica")
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Habitica binary sensor platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("fixture", "entity_state", "entity_picture"),
    [
        ("user", STATE_ON, f"{ASSETS_URL}inventory_quest_scroll_dustbunnies.png"),
        ("quest_invitation_off", STATE_OFF, None),
    ],
)
async def test_pending_quest_states(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    fixture: str,
    entity_state: str,
    entity_picture: str | None,
) -> None:
    """Test states of pending quest sensor."""

    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user",
        json=load_json_object_fixture(f"{fixture}.json", DOMAIN),
    )
    aioclient_mock.get(f"{DEFAULT_URL}/api/v3/tasks/user", json={"data": []})
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/content",
        params={"language": "en"},
        json=load_json_object_fixture("content.json", DOMAIN),
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        state := hass.states.get("binary_sensor.test_user_pending_quest_invitation")
    )
    assert state.state == entity_state
    assert state.attributes.get("entity_picture") == entity_picture
