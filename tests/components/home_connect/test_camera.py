"""Tests for home_connect camera entities."""

import asyncio
from collections.abc import Awaitable, Callable, Generator
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfImages,
    Event,
    EventKey,
    EventMessage,
    EventType,
    HomeAppliance,
)
from aiohomeconnect.model.error import HomeConnectApiError, TooManyRequestsError
from aiohomeconnect.model.image import Image
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import CameraState, async_get_image
from homeassistant.components.home_connect.const import (
    BSH_DOOR_STATE_CLOSED,
    DOMAIN,
    IMAGES_REFRESH_DELAY,
    REFRIGERATION_STATUS_DOOR_CLOSED,
    REFRIGERATION_STATUS_DOOR_OPEN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import MOCK_IMAGE_CONTENT, MOCK_IMAGES

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator

DOOR_CAMERA_KEY = "Refrigeration.FridgeFreezer.Status.DoorCameraPresentRefrigerator"
INTERIOR_CAMERA_KEY = (
    "Refrigeration.FridgeFreezer.Status.InteriorCameraPresentRefrigerator"
)
DOOR_CAMERA_ENTITY_ID = "camera.fridgefreezer_refrigerator_door_camera"
INTERIOR_CAMERA_ENTITY_ID = "camera.fridgefreezer_refrigerator_interior_camera"

NEW_DOOR_IMAGE = Image(
    key=DOOR_CAMERA_KEY,
    image_key="door-image-3",
    timestamp=1457711846,
    quality="good",
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CAMERA]


@pytest.fixture(autouse=True)
def mock_camera_access_token() -> Generator[None]:
    """Mock the camera access token which normally is randomized."""
    with patch(
        "homeassistant.components.camera.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


def _get_door_event(
    appliance: HomeAppliance,
    value: str,
    key: EventKey = EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
) -> EventMessage:
    """Return a door status event, for the refrigerator door by default."""
    return EventMessage(
        appliance.ha_id,
        EventType.STATUS,
        ArrayOfEvents(
            [
                Event(
                    key=key,
                    raw_key=key.value,
                    timestamp=0,
                    level="",
                    handling="",
                    value=value,
                )
            ]
        ),
    )


def _get_fridge_images() -> list[Image]:
    """Return the images of the fridge freezer fixture."""
    return ArrayOfImages.from_dict(MOCK_IMAGES["FridgeFreezer"]).images


async def _wait_for_images_refresh(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Wait for the delayed images refresh to run."""
    freezer.tick(timedelta(seconds=IMAGES_REFRESH_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test device removal and re-addition on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
@pytest.mark.parametrize(
    "exception",
    [
        HomeConnectApiError("SDK.Error.HomeAppliance.Connection.Initialization.Failed"),
        TooManyRequestsError("error.key", retry_after=42),
    ],
)
async def test_connected_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    exception: Exception,
) -> None:
    """Test that the camera entities are added once the images can be fetched.

    Fetching the images is optional, so failures and rate limits must not make
    the appliance refresh retry.
    """
    get_images_original_mock = client.get_images
    client.get_images = AsyncMock(side_effect=exception)
    with patch(
        "homeassistant.components.home_connect.coordinator.asyncio_sleep",
    ) as asyncio_sleep_mock:
        assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    asyncio_sleep_mock.assert_not_called()
    client.get_images.assert_called_once_with(appliance.ha_id)
    client.get_images = get_images_original_mock

    for key in (DOOR_CAMERA_KEY, INTERIOR_CAMERA_KEY):
        assert not entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{appliance.ha_id}-{key}"
        )

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for key in (DOOR_CAMERA_KEY, INTERIOR_CAMERA_KEY):
        assert entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"{appliance.ha_id}-{key}"
        )


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_camera_entity_availability(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test camera entities availability based on appliance connection."""
    entity_ids = [DOOR_CAMERA_ENTITY_ID, INTERIOR_CAMERA_ENTITY_ID]
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, CameraState.IDLE)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DISCONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, CameraState.IDLE)


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_images_kept_on_connected_refresh_error(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that the cameras stay available if fetching the images fails on reconnect."""
    entity_ids = [DOOR_CAMERA_ENTITY_ID, INTERIOR_CAMERA_ENTITY_ID]
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, CameraState.IDLE)

    client.get_images = AsyncMock(
        side_effect=HomeConnectApiError("error.key", "error description")
    )
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.CONNECTED,
                ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    client.get_images.assert_called_once_with(appliance.ha_id)
    for entity_id in entity_ids:
        assert hass.states.is_state(entity_id, CameraState.IDLE)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all camera entities to fixate the full set and their attributes."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("appliance", ["Dishwasher"], indirect=True)
async def test_appliance_without_cameras(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that images are not fetched for appliances that cannot have cameras."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_images.assert_not_called()
    assert not hass.states.async_all(Platform.CAMERA)


@pytest.mark.parametrize("appliance", ["Oven"], indirect=True)
async def test_unknown_camera(
    hass: HomeAssistant,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that cameras unknown to the integration are named after their key."""
    client.get_images = AsyncMock(
        return_value=ArrayOfImages(
            [
                Image(
                    key="Cooking.Oven.Status.CavityCamera",
                    image_key="oven-image-1",
                    timestamp=1457704646,
                    quality="good",
                )
            ]
        )
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("camera.oven_cavity_camera")
    assert state
    assert state.state == CameraState.IDLE
    assert state.attributes["friendly_name"] == "Oven Cavity camera"


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_camera_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that the latest image of the camera is served and cached."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    http_client = await hass_client()
    for _ in range(2):
        response = await http_client.get(f"/api/camera_proxy/{DOOR_CAMERA_ENTITY_ID}")
        assert response.status == HTTPStatus.OK
        assert response.content_type == "image/jpeg"
        assert await response.read() == MOCK_IMAGE_CONTENT

    client.get_image.assert_called_once_with(appliance.ha_id, image_key="door-image-2")


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_camera_image_concurrent_requests(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that concurrent requests for the same image download it only once."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    http_client = await hass_client()
    responses = await asyncio.gather(
        *(
            http_client.get(f"/api/camera_proxy/{DOOR_CAMERA_ENTITY_ID}")
            for _ in range(3)
        )
    )
    for response in responses:
        assert response.status == HTTPStatus.OK
        assert await response.read() == MOCK_IMAGE_CONTENT

    client.get_image.assert_called_once_with(appliance.ha_id, image_key="door-image-2")


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_camera_image_replaced_while_downloading(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that an image that is replaced while being downloaded is not cached."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    download_started = asyncio.Event()
    download_unblocked = asyncio.Event()

    async def get_image_side_effect(ha_id: str, image_key: str) -> bytes:
        """Block the download until the test unblocks it."""
        download_started.set()
        await download_unblocked.wait()
        return image_key.encode()

    client.get_image = AsyncMock(side_effect=get_image_side_effect)
    # Use a timeout longer than the images refresh delay, as the time is frozen
    stale_request = asyncio.create_task(
        async_get_image(hass, DOOR_CAMERA_ENTITY_ID, timeout=IMAGES_REFRESH_DELAY * 2)
    )
    await download_started.wait()

    # A new image is taken while the old one is being downloaded
    client.get_images = AsyncMock(
        return_value=ArrayOfImages([*_get_fridge_images(), NEW_DOOR_IMAGE])
    )
    await client.add_events(
        [_get_door_event(appliance, REFRIGERATION_STATUS_DOOR_CLOSED)]
    )
    await hass.async_block_till_done()
    await _wait_for_images_refresh(hass, freezer)

    download_unblocked.set()
    assert (await stale_request).content == b"door-image-2"

    assert (
        await async_get_image(hass, DOOR_CAMERA_ENTITY_ID)
    ).content == b"door-image-3"
    assert client.get_image.call_count == 2


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_camera_image_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
) -> None:
    """Test that an error fetching the image is reported to the requester."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_image = AsyncMock(
        side_effect=HomeConnectApiError("error.key", "error description")
    )
    http_client = await hass_client()
    response = await http_client.get(f"/api/camera_proxy/{DOOR_CAMERA_ENTITY_ID}")
    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_new_image_after_door_closed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that a new image taken after closing the door replaces the old one."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    http_client = await hass_client()
    response = await http_client.get(f"/api/camera_proxy/{DOOR_CAMERA_ENTITY_ID}")
    assert response.status == HTTPStatus.OK
    client.get_image.assert_called_once_with(appliance.ha_id, image_key="door-image-2")

    client.get_images = AsyncMock(
        return_value=ArrayOfImages([*_get_fridge_images(), NEW_DOOR_IMAGE])
    )
    await client.add_events(
        [_get_door_event(appliance, REFRIGERATION_STATUS_DOOR_CLOSED)]
    )
    await hass.async_block_till_done()
    client.get_images.assert_not_called()

    await _wait_for_images_refresh(hass, freezer)

    client.get_images.assert_called_once_with(appliance.ha_id)

    response = await http_client.get(f"/api/camera_proxy/{DOOR_CAMERA_ENTITY_ID}")
    assert response.status == HTTPStatus.OK
    client.get_image.assert_called_with(appliance.ha_id, image_key="door-image-3")

    response = await http_client.get(f"/api/camera_proxy/{INTERIOR_CAMERA_ENTITY_ID}")
    assert response.status == HTTPStatus.OK
    client.get_image.assert_called_with(appliance.ha_id, image_key="interior-image-1")


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
@pytest.mark.parametrize(
    ("door_event_key", "door_states", "expected_images_fetches"),
    [
        pytest.param(
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            [REFRIGERATION_STATUS_DOOR_CLOSED],
            1,
            id="door_closed",
        ),
        pytest.param(
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            [REFRIGERATION_STATUS_DOOR_OPEN],
            0,
            id="door_open",
        ),
        pytest.param(
            EventKey.REFRIGERATION_COMMON_STATUS_DOOR_REFRIGERATOR,
            [REFRIGERATION_STATUS_DOOR_CLOSED, REFRIGERATION_STATUS_DOOR_CLOSED],
            1,
            id="door_closed_twice",
        ),
        pytest.param(
            EventKey.BSH_COMMON_STATUS_DOOR_STATE,
            [BSH_DOOR_STATE_CLOSED],
            1,
            id="generic_door_closed",
        ),
    ],
)
async def test_images_refresh_scheduling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    door_event_key: EventKey,
    door_states: list[str],
    expected_images_fetches: int,
) -> None:
    """Test that the images are only refreshed once after the door is closed."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED
    client.get_images.reset_mock()

    await client.add_events(
        [
            _get_door_event(appliance, door_state, door_event_key)
            for door_state in door_states
        ]
    )
    await hass.async_block_till_done()
    await _wait_for_images_refresh(hass, freezer)

    assert client.get_images.call_count == expected_images_fetches


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
@pytest.mark.parametrize(
    "exception",
    [
        HomeConnectApiError("error.key", "error description"),
        TooManyRequestsError("error.key", retry_after=0),
    ],
)
async def test_images_refresh_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
    exception: Exception,
) -> None:
    """Test that the current images are kept when the refresh fails."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_images = AsyncMock(side_effect=exception)
    await client.add_events(
        [_get_door_event(appliance, REFRIGERATION_STATUS_DOOR_CLOSED)]
    )
    await hass.async_block_till_done()
    await _wait_for_images_refresh(hass, freezer)

    client.get_images.assert_called_once_with(appliance.ha_id)
    assert hass.states.is_state(DOOR_CAMERA_ENTITY_ID, CameraState.IDLE)

    http_client = await hass_client()
    response = await http_client.get(f"/api/camera_proxy/{DOOR_CAMERA_ENTITY_ID}")
    assert response.status == HTTPStatus.OK
    client.get_image.assert_called_once_with(appliance.ha_id, image_key="door-image-2")


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_new_camera_after_door_closed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that an entity is added for a camera that takes its first image."""
    fridge_images = _get_fridge_images()
    client.get_images = AsyncMock(
        return_value=ArrayOfImages(
            [image for image in fridge_images if image.key == DOOR_CAMERA_KEY]
        )
    )
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(DOOR_CAMERA_ENTITY_ID, CameraState.IDLE)
    assert not hass.states.get(INTERIOR_CAMERA_ENTITY_ID)

    client.get_images = AsyncMock(return_value=ArrayOfImages(fridge_images))
    await client.add_events(
        [_get_door_event(appliance, REFRIGERATION_STATUS_DOOR_CLOSED)]
    )
    await hass.async_block_till_done()
    await _wait_for_images_refresh(hass, freezer)

    assert hass.states.is_state(DOOR_CAMERA_ENTITY_ID, CameraState.IDLE)
    assert hass.states.is_state(INTERIOR_CAMERA_ENTITY_ID, CameraState.IDLE)


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_removed_camera_after_door_closed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that a camera that stops reporting images becomes unavailable."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.is_state(DOOR_CAMERA_ENTITY_ID, CameraState.IDLE)
    assert hass.states.is_state(INTERIOR_CAMERA_ENTITY_ID, CameraState.IDLE)

    fridge_images = _get_fridge_images()
    client.get_images = AsyncMock(
        return_value=ArrayOfImages(
            [image for image in fridge_images if image.key == DOOR_CAMERA_KEY]
        )
    )
    await client.add_events(
        [_get_door_event(appliance, REFRIGERATION_STATUS_DOOR_CLOSED)]
    )
    await hass.async_block_till_done()
    await _wait_for_images_refresh(hass, freezer)

    assert hass.states.is_state(DOOR_CAMERA_ENTITY_ID, CameraState.IDLE)
    assert hass.states.is_state(INTERIOR_CAMERA_ENTITY_ID, STATE_UNAVAILABLE)

    client.get_images = AsyncMock(return_value=ArrayOfImages(fridge_images))
    await client.add_events(
        [_get_door_event(appliance, REFRIGERATION_STATUS_DOOR_CLOSED)]
    )
    await hass.async_block_till_done()
    await _wait_for_images_refresh(hass, freezer)

    assert hass.states.is_state(DOOR_CAMERA_ENTITY_ID, CameraState.IDLE)
    assert hass.states.is_state(INTERIOR_CAMERA_ENTITY_ID, CameraState.IDLE)
