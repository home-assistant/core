"""Test the PlayStation Network image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import respx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def image_only() -> Generator[None]:
    """Enable only the image platform."""
    with patch(
        "homeassistant.components.playstation_network.PLATFORMS",
        [Platform.IMAGE],
    ):
        yield


@respx.mock
@pytest.mark.usefixtures("mock_psnawpapi")
async def test_image_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test image platform."""
    freezer.move_to("2025-06-16T00:00:00-00:00")

    respx.get(
        "http://static-resource.np.community.playstation.net/avatar_xl/WWS_A/UP90001312L24_DD96EB6A4FF5FE883C09_XL.png"
    ).respond(status_code=HTTPStatus.OK, content_type="image/png", content=b"Test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("image.testuser_avatar"))
    assert state.state == "2025-06-16T00:00:00+00:00"

    access_token = state.attributes["access_token"]
    assert (
        state.attributes["entity_picture"]
        == f"/api/image_proxy/image.testuser_avatar?token={access_token}"
    )

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test"
    assert resp.content_type == "image/png"
    assert resp.content_length == 4

    ava = "https://static-resource.np.community.playstation.net/avatar_m/WWS_E/E0011_m.png"
    profile = mock_psnawpapi.user.return_value.profile.return_value
    profile["avatars"] = [{"size": "xl", "url": ava}]
    mock_psnawpapi.user.return_value.profile.return_value = profile
    respx.get(ava).respond(
        status_code=HTTPStatus.OK, content_type="image/png", content=b"Test2"
    )

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert (state := hass.states.get("image.testuser_avatar"))
    assert state.state == "2025-06-16T00:00:30+00:00"

    access_token = state.attributes["access_token"]
    assert (
        state.attributes["entity_picture"]
        == f"/api/image_proxy/image.testuser_avatar?token={access_token}"
    )

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test2"
    assert resp.content_type == "image/png"
    assert resp.content_length == 5
