"""Test the Litter-Robot image entity."""

from collections.abc import Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import create_mock_account, setup_integration

IMAGE_ENTITY_ID = "image.kitty"
IMAGE_URL = "https://example.com/PET-123/profile.jpg"
NEW_IMAGE_URL = "https://example.com/PET-123/profile2.jpg"


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock the image access token, which is normally random."""
    with patch(
        "homeassistant.components.image.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


async def _setup_image_platform(
    hass: HomeAssistant, mock_account: MagicMock
) -> ConfigEntry:
    with patch("homeassistant.components.litterrobot.PLATFORMS", [Platform.IMAGE]):
        return await setup_integration(hass, mock_account)


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.freeze_time("2026-11-10 12:00:00")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_account_with_pet: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the pet image entities."""
    entry = await _setup_image_platform(hass, mock_account_with_pet)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_pet_without_image(hass: HomeAssistant) -> None:
    """Test a pet without a profile image has no image entity."""
    account = create_mock_account(pet=True)
    account.pets[0]._data["profileImage"] = None
    await _setup_image_platform(hass, account)

    assert hass.states.get(IMAGE_ENTITY_ID) is None


@respx.mock
@pytest.mark.freeze_time("2026-11-10 12:00:00")
async def test_image_url_change(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_account_with_pet: MagicMock,
) -> None:
    """Test the image is fetched and refreshed when the url changes."""
    respx.get(IMAGE_URL).respond(
        status_code=HTTPStatus.OK, content_type="image/jpeg", content=b"Test"
    )
    respx.get(NEW_IMAGE_URL).respond(
        status_code=HTTPStatus.OK, content_type="image/jpeg", content=b"Test2"
    )
    await _setup_image_platform(hass, mock_account_with_pet)

    assert (state := hass.states.get(IMAGE_ENTITY_ID))
    assert state.state == "2026-11-10T12:00:00+00:00"

    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"Test"

    # An unchanged url keeps the cached image and timestamp.
    await _refresh(hass, freezer)
    assert (state := hass.states.get(IMAGE_ENTITY_ID))
    assert state.state == "2026-11-10T12:00:00+00:00"

    mock_account_with_pet.pets[0]._data["profileImage"]["s3ImageURL"] = NEW_IMAGE_URL
    await _refresh(hass, freezer)

    assert (state := hass.states.get(IMAGE_ENTITY_ID))
    assert state.state == "2026-11-10T12:10:00+00:00"

    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    assert await resp.read() == b"Test2"


async def test_pet_image_added_later(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test an image entity is added once a pet gets a profile image."""
    account = create_mock_account(pet=True)
    pet = account.pets[0]
    pet._data["profileImage"] = None
    await _setup_image_platform(hass, account)

    assert hass.states.get(IMAGE_ENTITY_ID) is None

    pet._data["profileImage"] = {"imagePath": "path", "s3ImageURL": IMAGE_URL}
    await _refresh(hass, freezer)

    assert hass.states.get(IMAGE_ENTITY_ID) is not None
