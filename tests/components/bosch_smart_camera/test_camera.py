"""Test the Bosch Smart Camera setup, coordinator and camera platform."""

import asyncio
from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
    Camera,
    CameraModel,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_smart_camera.const import DOMAIN
from homeassistant.components.bosch_smart_camera.coordinator import (
    SCAN_INTERVAL,
    SNAPSHOT_TTL,
)
from homeassistant.components.camera import async_get_image
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestConnectionError,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import CAMERA_ID, CAMERAS

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "camera.garden"
OTHER_ID = "22222222-2222-2222-2222-222222222222"
OTHER = Camera(OTHER_ID, "Hall", "SOMETHING_NEW", CameraModel.UNKNOWN, None)


async def test_camera_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a camera entity and its device are created from the list."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == "idle"
    assert entity_registry.async_get(ENTITY_ID).unique_id == CAMERA_ID
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERA_ID), mock_config_entry.entry_id
    )
    assert device.name == "Garden"
    assert device.manufacturer == "Bosch"
    assert device.model == "Eyes Outdoor II"
    assert device.sw_version == "9.40.25"


async def test_unknown_model_uses_hardware_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a model outside the known lineup falls back to the raw value."""
    mock_list_cameras.return_value = [OTHER]
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, OTHER_ID), mock_config_entry.entry_id
    )
    assert device.model == "SOMETHING_NEW"
    assert device.sw_version is None


@pytest.fixture
def mock_latest_image() -> Generator[AsyncMock]:
    """Mock the latest event image of the library."""
    with patch(
        "homeassistant.components.bosch_smart_camera.coordinator.get_latest_event_image",
        autospec=True,
        return_value=b"jpeg-1",
    ) as mock:
        yield mock


async def test_camera_image_is_the_latest_event_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_latest_image: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the image is cached briefly and fetched again afterwards."""
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, ENTITY_ID)
    assert image.content == b"jpeg-1"
    assert mock_latest_image.await_args.args[1:] == ("fake-access-token", CAMERAS[0].id)

    mock_latest_image.return_value = b"jpeg-2"
    assert (await async_get_image(hass, ENTITY_ID)).content == b"jpeg-1"
    assert mock_latest_image.await_count == 1

    freezer.tick(timedelta(seconds=SNAPSHOT_TTL + 1))
    assert (await async_get_image(hass, ENTITY_ID)).content == b"jpeg-2"


async def test_camera_image_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_latest_image: AsyncMock,
) -> None:
    """Test a camera without any event image has no image."""
    mock_latest_image.return_value = None
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, ENTITY_ID)


async def test_missing_image_is_cached_briefly(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_latest_image: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a camera without an event image is not asked again within the TTL."""
    mock_latest_image.return_value = None
    await setup_integration(hass, mock_config_entry)

    for _ in range(2):
        with pytest.raises(HomeAssistantError):
            await async_get_image(hass, ENTITY_ID)
    assert mock_latest_image.await_count == 1

    freezer.tick(timedelta(seconds=SNAPSHOT_TTL + 1))
    mock_latest_image.return_value = b"jpeg-1"
    assert (await async_get_image(hass, ENTITY_ID)).content == b"jpeg-1"


async def test_slow_download_does_not_block_other_cameras(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_latest_image: AsyncMock,
) -> None:
    """Test one camera's slow image request does not hold up another camera."""
    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    release = asyncio.Event()

    async def fetch(session, token, camera_id):
        if camera_id == CAMERA_ID:
            await release.wait()
        return camera_id.encode()

    mock_latest_image.side_effect = fetch
    await setup_integration(hass, mock_config_entry)

    slow = hass.async_create_task(async_get_image(hass, ENTITY_ID))
    await asyncio.sleep(0)
    assert (await async_get_image(hass, "camera.hall")).content == OTHER_ID.encode()
    assert not slow.done()
    release.set()
    assert (await slow).content == CAMERA_ID.encode()


async def test_token_refresh_failure_surfaces_translated_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_latest_image: AsyncMock,
) -> None:
    """Test a failing token refresh makes the image request fail cleanly."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
            side_effect=OAuth2TokenRequestConnectionError(domain=DOMAIN),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await async_get_image(hass, ENTITY_ID)


@pytest.mark.parametrize(
    "error",
    [
        BoschCameraAuthError,
        BoschCameraConnectionError,
        BoschCameraInvalidResponseError,
    ],
)
async def test_camera_image_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_latest_image: AsyncMock,
    error: type[Exception],
) -> None:
    """Test library errors surface as a translated error and are not cached."""
    mock_latest_image.side_effect = error
    await setup_integration(hass, mock_config_entry)

    for _ in range(2):
        with pytest.raises(HomeAssistantError) as err:
            await async_get_image(hass, ENTITY_ID)
        assert err.value.translation_key == "snapshot_failed"
    assert mock_latest_image.await_count == 2


@patch("homeassistant.components.bosch_smart_camera.coordinator.SNAPSHOT_TTL", 3600)
async def test_removed_camera_forgets_its_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    mock_latest_image: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a camera that left the account and returns is asked again."""
    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    await setup_integration(hass, mock_config_entry)
    await async_get_image(hass, "camera.hall")
    assert mock_latest_image.await_count == 1

    mock_list_cameras.return_value = list(CAMERAS)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is None

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await async_get_image(hass, "camera.hall")
    assert mock_latest_image.await_count == 2


async def test_unload(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test the entry unloads."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (BoschCameraConnectionError, ConfigEntryState.SETUP_RETRY),
        (BoschCameraInvalidResponseError, ConfigEntryState.SETUP_RETRY),
        (BoschCameraAuthError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    error: type[Exception],
    state: ConfigEntryState,
) -> None:
    """Test library errors map to retry or a setup error."""
    mock_list_cameras.side_effect = error
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_update_failure_makes_camera_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing poll marks the camera unavailable and recovers."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.side_effect = BoschCameraConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_list_cameras.side_effect = None
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "idle"


async def test_device_name_and_firmware_follow_the_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a rename or firmware update in the account reaches the device."""
    await setup_integration(hass, mock_config_entry)

    mock_list_cameras.return_value = [
        replace(CAMERAS[0], title="Patio", firmware_version="9.40.26")
    ]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERAS[0].id), mock_config_entry.entry_id
    )
    assert device.name == "Patio"
    assert device.sw_version == "9.40.26"


async def test_camera_added_and_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_list_cameras: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test cameras appear and disappear with the account."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("camera.hall") is None

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is not None
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, OTHER_ID), mock_config_entry.entry_id
    )

    mock_list_cameras.return_value = list(CAMERAS)
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, OTHER_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert hass.states.get(ENTITY_ID).state == "idle"

    mock_list_cameras.return_value = [*CAMERAS, OTHER]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("camera.hall") is not None


async def test_stale_device_removed_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device of a camera removed while Home Assistant was off is dropped."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, OTHER_ID)},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, OTHER_ID), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, CAMERA_ID), mock_config_entry.entry_id
    )
