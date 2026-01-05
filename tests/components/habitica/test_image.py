"""Tests for the Habitica image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from io import BytesIO
import sys
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from habiticalib import HabiticaGroupsResponse, HabiticaUserResponse
import pytest
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import ASSETS_URL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed, async_load_fixture
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def image_only() -> Generator[None]:
    """Enable only the image platform."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [Platform.IMAGE],
    ):
        yield


@pytest.mark.skipif(
    sys.platform != "linux", reason="linux only"
)  # Pillow output on win/mac is different
async def test_image_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
    habitica: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test image platform."""
    freezer.move_to("2024-09-20T22:00:00.000")
    with patch(
        "homeassistant.components.habitica.coordinator.BytesIO",
    ) as avatar:
        avatar.side_effect = [
            BytesIO(b"\x89PNGTestImage1"),
            BytesIO(b"\x89PNGTestImage2"),
        ]

        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED

        assert (state := hass.states.get("image.test_user_avatar"))
        assert state.state == "2024-09-20T22:00:00+00:00"

        access_token = state.attributes["access_token"]
        assert (
            state.attributes["entity_picture"]
            == f"/api/image_proxy/image.test_user_avatar?token={access_token}"
        )

        client = await hass_client()
        resp = await client.get(state.attributes["entity_picture"])
        assert resp.status == HTTPStatus.OK

        assert (await resp.read()) == b"\x89PNGTestImage1"

        habitica.get_user.return_value = HabiticaUserResponse.from_json(
            await async_load_fixture(hass, "rogue_fixture.json", DOMAIN)
        )

        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert (state := hass.states.get("image.test_user_avatar"))
        assert state.state == "2024-09-20T22:01:00+00:00"

        resp = await client.get(state.attributes["entity_picture"])
        assert resp.status == HTTPStatus.OK

        assert (await resp.read()) == b"\x89PNGTestImage2"


@pytest.mark.usefixtures("habitica")
@respx.mock
async def test_load_image_from_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test loading of image from URL."""
    freezer.move_to("2024-09-20T22:00:00.000")

    call1 = respx.get(f"{ASSETS_URL}quest_atom1.png").respond(content=b"\x89PNG")
    call2 = respx.get(f"{ASSETS_URL}quest_dustbunnies.png").respond(content=b"\x89PNG")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("image.test_user_s_party_quest"))
    assert state.state == "2024-09-20T22:00:00+00:00"

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.OK

    assert (await resp.read()) == b"\x89PNG"

    assert call1.call_count == 1

    habitica.get_group.return_value = HabiticaGroupsResponse.from_json(
        await async_load_fixture(hass, "party_2.json", DOMAIN)
    )
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("image.test_user_s_party_quest"))
    assert state.state == "2024-09-20T22:15:00+00:00"

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.OK

    assert (await resp.read()) == b"\x89PNG"
    assert call2.call_count == 1


@pytest.mark.usefixtures("habitica")
@respx.mock
async def test_load_image_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test NotFound error."""
    freezer.move_to("2024-09-20T22:00:00.000")

    call1 = respx.get(f"{ASSETS_URL}quest_atom1.png").respond(status_code=404)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("image.test_user_s_party_quest"))
    assert state.state == "2024-09-20T22:00:00+00:00"

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR

    assert call1.call_count == 1
