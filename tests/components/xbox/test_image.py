"""Test the Xbox image platform."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import respx
from syrupy.assertion import SnapshotAssertion
from xbox.webapi.api.provider.people.models import PeopleResponse

from homeassistant.components.xbox.const import DOMAIN
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
        "homeassistant.components.xbox.PLATFORMS",
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


@pytest.mark.usefixtures("xbox_live_client")
@pytest.mark.freeze_time("2013-12-13 12:13:12")
async def test_image_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the Xbox image platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@respx.mock
async def test_load_image_from_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    xbox_live_client: AsyncMock,
) -> None:
    """Test image platform loads image from url."""

    freezer.move_to("2025-06-16T00:00:00-00:00")

    respx.get(
        "https://images-eds-ssl.xboxlive.com/image?url=wHwbXKif8cus8csoZ03RW_ES.ojiJijNBGRVUbTnZKsoCCCkjlsEJrrMqDkYqs3M0aLOK2"
        "kxE9mbLm9M2.R0stAQYoDsGCDJxqDzG9WF3oa4rOCjEK7DbZXdBmBWnMrfErA3M_Q4y_mUTEQLqSAEeYFGlGeCXYsccnQMvEecxRg-&format=png"
    ).respond(status_code=HTTPStatus.OK, content_type="image/png", content=b"Test")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("image.gsr_ae_gamerpic"))
    assert state.state == "2025-06-16T00:00:00+00:00"

    access_token = state.attributes["access_token"]
    assert (
        state.attributes["entity_picture"]
        == f"/api/image_proxy/image.gsr_ae_gamerpic?token={access_token}"
    )

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test"
    assert resp.content_type == "image/png"
    assert resp.content_length == 4

    xbox_live_client.people.get_friends_own_batch.return_value = PeopleResponse(
        **await async_load_json_object_fixture(
            hass, "people_batch gamerpic.json", DOMAIN
        )  # pyright: ignore[reportArgumentType]
    )

    respx.get(
        "https://images-eds-ssl.xboxlive.com/image?url=KT_QTPJeC5ZpnbX.xahcbrZ9enA_IV9WfFEWIqHGUb5P30TpCdy9xIzUMuqZVCfbWmxtVC"
        "rgWHJigthrlsHCxEOMG9UGNdojCYasYt6MJHBjmxmtuAHJeo.sOkUiPmg4JHXvOS82c3UOrvdJTDaCKwCwHPJ0t0Plha8oHFC1i_o-&format=png"
    ).respond(status_code=HTTPStatus.OK, content_type="image/png", content=b"Test2")

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("image.gsr_ae_gamerpic"))
    assert state.state == "2025-06-16T00:00:10+00:00"

    access_token = state.attributes["access_token"]
    assert (
        state.attributes["entity_picture"]
        == f"/api/image_proxy/image.gsr_ae_gamerpic?token={access_token}"
    )

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test2"
    assert resp.content_type == "image/png"
    assert resp.content_length == 5
