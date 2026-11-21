"""Tests for miele image module."""

import asyncio
import base64
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, Mock

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.image import async_get_image
from homeassistant.components.miele.const import StateStatus
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.parametrize("platforms", [(Platform.IMAGE,)])

ENTITY_ID = "image.oven_camera"
RAW_IMAGE_BYTES = b"\xff\xd8\xff\xe0test-jpeg-bytes"


@pytest.fixture
def active_oven(device_fixture: dict[str, Any]) -> None:
    """Set the oven fixture status to in use."""
    device_fixture["DummyOven"]["state"]["status"]["value_raw"] = (
        StateStatus.in_use.value
    )


@pytest.fixture
def oven_status(device_fixture: dict[str, Any], status: StateStatus) -> None:
    """Set the oven fixture status."""
    device_fixture["DummyOven"]["state"]["status"]["value_raw"] = status.value


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.parametrize(
    "status",
    [StateStatus.off, StateStatus.on, StateStatus.program_ended],
)
async def test_image_unavailable_when_oven_not_running(
    hass: HomeAssistant,
    oven_status: None,
    mock_miele_client: MagicMock,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test image entity is unavailable when oven (type 12) is not running."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert ATTR_ENTITY_PICTURE not in state.attributes

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == "DummyOven-camera"

    with pytest.raises(
        HomeAssistantError, match=f"Unable to get image from {ENTITY_ID}"
    ):
        await async_get_image(hass, ENTITY_ID)
    mock_miele_client.get_camera.assert_not_called()


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.usefixtures("active_oven")
async def test_image_entity_created(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test image entity is created and available when oven is active."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == "DummyOven-camera"


@pytest.mark.parametrize("load_device_file", ["hob.json"])
async def test_image_not_created_for_non_oven(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test image entity is not created for non-oven appliances."""
    assert entity_registry.async_get(ENTITY_ID) is None


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.usefixtures("active_oven")
async def test_image_raw_base64(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test fetching image from raw base64 payload and serving from cache."""
    mock_miele_client.get_camera.return_value = {
        "image": base64.b64encode(RAW_IMAGE_BYTES).decode("ascii")
    }

    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == RAW_IMAGE_BYTES
    assert image.content_type == "image/jpeg"

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
    first_state = state.state

    # Second call within cache TTL should not hit the API or update state again
    cached_image = await async_get_image(hass, ENTITY_ID)
    assert cached_image.content == RAW_IMAGE_BYTES
    mock_miele_client.get_camera.assert_called_once_with("DummyOven")
    assert hass.states.get(ENTITY_ID).state == first_state


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.usefixtures("active_oven")
async def test_image_data_uri_and_content_type_reset(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    setup_platform: MockConfigEntry,
) -> None:
    """Test data URI content type and resetting to JPEG on subsequent raw response."""
    png_bytes = b"\x89PNG\r\n\x1a\ntest-png-bytes"
    png_encoded = base64.b64encode(png_bytes).decode("ascii")
    jpeg_encoded = base64.b64encode(RAW_IMAGE_BYTES).decode("ascii")

    mock_miele_client.get_camera.side_effect = [
        {"image": f"data:image/png;base64,{png_encoded}"},
        {"image": jpeg_encoded},
    ]

    first_image = await async_get_image(hass, ENTITY_ID)
    assert first_image.content == png_bytes
    assert first_image.content_type == "image/png"

    freezer.tick(timedelta(seconds=61))

    second_image = await async_get_image(hass, ENTITY_ID)
    assert second_image.content == RAW_IMAGE_BYTES
    assert second_image.content_type == "image/jpeg"

    assert mock_miele_client.get_camera.call_count == 2


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.usefixtures("active_oven")
@pytest.mark.parametrize(
    ("api_return", "api_side_effect"),
    [
        ({"image": None}, None),
        ({"image": ""}, None),
        ({"image": "not-valid-base64!@#"}, None),
        (None, ClientResponseError(Mock(), Mock())),
        (None, TimeoutError()),
    ],
)
async def test_image_errors(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
    api_return: dict[str, str | None] | None,
    api_side_effect: Exception | None,
) -> None:
    """Test handling of missing, invalid, or failing image responses."""
    mock_miele_client.get_camera.return_value = api_return
    mock_miele_client.get_camera.side_effect = api_side_effect

    with pytest.raises(
        HomeAssistantError, match=f"Unable to get image from {ENTITY_ID}"
    ):
        await async_get_image(hass, ENTITY_ID)
    mock_miele_client.get_camera.assert_called_once_with("DummyOven")


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.usefixtures("active_oven")
async def test_image_concurrent_requests_use_lock(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: MockConfigEntry,
) -> None:
    """Test concurrent image requests share a single API call via the entity lock."""
    encoded = base64.b64encode(RAW_IMAGE_BYTES).decode("ascii")

    async def delayed_camera(_device_id: str) -> dict[str, str]:
        await asyncio.sleep(0)
        return {"image": encoded}

    mock_miele_client.get_camera.side_effect = delayed_camera

    first, second = await asyncio.gather(
        async_get_image(hass, ENTITY_ID),
        async_get_image(hass, ENTITY_ID),
    )
    assert first.content == RAW_IMAGE_BYTES
    assert second.content == RAW_IMAGE_BYTES
    mock_miele_client.get_camera.assert_called_once_with("DummyOven")


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.usefixtures("active_oven")
async def test_image_error_cooldown(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    setup_platform: MockConfigEntry,
) -> None:
    """Test failed camera fetches are throttled for the cooldown period."""
    encoded = base64.b64encode(RAW_IMAGE_BYTES).decode("ascii")
    mock_miele_client.get_camera.side_effect = [
        TimeoutError(),
        {"image": encoded},
    ]

    with pytest.raises(
        HomeAssistantError, match=f"Unable to get image from {ENTITY_ID}"
    ):
        await async_get_image(hass, ENTITY_ID)
    mock_miele_client.get_camera.assert_called_once_with("DummyOven")

    # Repeated request within cooldown does not hit the API again
    with pytest.raises(
        HomeAssistantError, match=f"Unable to get image from {ENTITY_ID}"
    ):
        await async_get_image(hass, ENTITY_ID)
    mock_miele_client.get_camera.assert_called_once_with("DummyOven")

    # After cooldown expires, a fresh request succeeds
    freezer.tick(timedelta(seconds=61))
    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == RAW_IMAGE_BYTES
    assert mock_miele_client.get_camera.call_count == 2
