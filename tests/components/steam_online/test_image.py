"""Tests for Steam image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.steam_online.const import DOMAIN, STEAM_API_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def image_only() -> Generator[None]:
    """Enable only the image platform."""
    with patch(
        "homeassistant.components.steam_online.PLATFORMS",
        [Platform.IMAGE],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_getrandbits():
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1312,
    ):
        yield


@pytest.mark.usefixtures("steam_api", "entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2013-12-13 12:13:12")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Steam sensor platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@respx.mock
@pytest.mark.freeze_time("2013-12-13 12:13:12")
async def test_load_image_from_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    steam_api: MagicMock,
) -> None:
    """Test image platform loads image from url."""

    respx.get(f"{STEAM_API_URL}20900/capsule_616x353.jpg").respond(
        status_code=HTTPStatus.OK, content_type="image/jpg", content=b"Test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("image.testaccount1_main_capsule"))
    assert state.state == "2013-12-13T12:13:12+00:00"

    access_token = state.attributes["access_token"]
    assert (
        state.attributes["entity_picture"]
        == f"/api/image_proxy/image.testaccount1_main_capsule?token={access_token}"
    )

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test"
    assert resp.content_type == "image/jpg"
    assert resp.content_length == 4

    steam_api.return_value.GetPlayerSummaries.return_value = (
        await async_load_json_object_fixture(hass, "GetPlayerSummaries2.json", DOMAIN)
    )

    respx.get(f"{STEAM_API_URL}1180660/capsule_616x353.jpg").respond(
        status_code=HTTPStatus.OK, content_type="image/jpg", content=b"Test2"
    )

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("image.testaccount1_main_capsule"))
    assert state.state == "2013-12-13T12:13:42+00:00"

    access_token = state.attributes["access_token"]
    assert (
        state.attributes["entity_picture"]
        == f"/api/image_proxy/image.testaccount1_main_capsule?token={access_token}"
    )

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test2"
    assert resp.content_type == "image/jpg"
    assert resp.content_length == 5
